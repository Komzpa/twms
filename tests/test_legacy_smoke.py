import datetime
import importlib
import importlib.metadata
import hashlib
import json
import math
import os
from io import BytesIO
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import warnings
from http.server import ThreadingHTTPServer
import xml.etree.ElementTree as ET
from unittest import mock

from PIL import Image

import twms
import twms.canvas
import twms.daemon
import twms.fetchers
import twms.filter
import twms.projections
import twms.server
import twms.twms


class LegacySmokeTest(unittest.TestCase):
    def image_bytes(self, color, image_format="PNG"):
        buffer = BytesIO()
        image = Image.new("RGBA", (256, 256), color)
        if image_format == "JPEG":
            image = image.convert("RGB")
        image.save(buffer, image_format)
        return buffer.getvalue()

    def cache_path(self, cache_root, layer, z, x, y):
        return os.path.join(
            cache_root,
            layer["prefix"],
            "z%s" % z,
            "%s" % (x // 1024),
            "x%s" % x,
            "%s" % (y // 1024),
            "y%s.%s" % (y, layer["ext"]),
        )

    def zxy_cache_path(self, cache_root, layer, z, x, y):
        return os.path.join(
            cache_root,
            layer["prefix"],
            "%s" % z,
            "%s" % x,
            "%s.%s" % (y, layer["ext"]),
        )

    def test_public_version_keeps_keyboard_suffix(self):
        self.assertEqual(twms.__version__, "0.07z")
        self.assertEqual(importlib.metadata.version("twms"), "0.7+z")

    def test_legacy_modules_import_as_package_modules(self):
        modules = [
            "twms.bbox",
            "twms.capabilities",
            "twms.correctify",
            "twms.drawing",
            "twms.filter",
            "twms.gpxparse",
            "twms.image_compat",
            "twms.josm",
            "twms.overview",
            "twms.projections",
            "twms.reproject",
            "twms.sketch",
            "twms.wmts",
        ]
        for module in modules:
            with self.subTest(module=module):
                importlib.import_module(module)

    def test_wms_capabilities_smoke(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "request": "GetCapabilities",
                "version": "1.1.1",
                "ref": "http://example.test/wms",
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/vnd.ogc.wms_xml")
        self.assertIn("<WMT_MS_Capabilities", body)
        self.assertIn("OpenStreetMap mapnik", body)
        self.assertNotIn("<SRS>CRS:84</SRS>", body)

    def test_wms_130_capabilities_smoke(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "SERVICE": "WMS",
                "REQUEST": "GetCapabilities",
                "VERSION": "1.3.0",
                "ref": "http://example.test/wms",
            }
        )

        root = ET.fromstring(body)
        namespaces = {"wms": "http://www.opengis.net/wms"}
        osm = root.find(
            "./wms:Capability/wms:Layer/wms:Layer[wms:Name='osm']",
            namespaces,
        )
        crs_values = [element.text for element in osm.findall("wms:CRS", namespaces)]
        bbox = osm.find("wms:BoundingBox", namespaces)

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/xml")
        self.assertEqual(root.tag, "{http://www.opengis.net/wms}WMS_Capabilities")
        self.assertEqual(root.attrib["version"], "1.3.0")
        self.assertIn("CRS:84", crs_values)
        self.assertIn("EPSG:3857", crs_values)
        self.assertEqual(bbox.attrib["CRS"], "EPSG:3857")
        self.assertLess(float(bbox.attrib["minx"]), -20000000)
        self.assertGreater(float(bbox.attrib["maxx"]), 20000000)

    def test_wms_getmap_accepts_crs_parameter(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "request": "GetMap",
                "layers": "transparent",
                "format": "image/png",
                "width": "32",
                "height": "32",
                "crs": "CRS:84",
                "bbox": "-1,-1,1,1",
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/png")
        with Image.open(BytesIO(body)) as image:
            self.assertEqual(image.size, (32, 32))

    def test_overview_smoke(self):
        status, content_type, body = twms.twms.twms_main({"ref": "http://example.test/"})

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/html")
        self.assertIn("<table>", body)
        self.assertIn("Yandex Satellite", body)

    def test_gettile_transparent_layer_smoke(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "request": "GetTile",
                "layers": "transparent",
                "format": "image/png",
                "z": "0",
                "x": "0",
                "y": "0",
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/png")
        with Image.open(BytesIO(body)) as image:
            self.assertEqual(image.size, (256, 256))
            self.assertEqual(image.mode, "RGBA")

    def test_legacy_getcorrections_without_rectify_file(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "request": "GetCorrections",
                "layers": "osm",
                "points": "27.6,53.2",
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/plain")
        self.assertEqual(body, "27.6,53.2;\n")

    def test_legacy_filter_smoke(self):
        image = Image.new("RGBA", (2, 1), (10, 20, 30, 255))

        filtered = twms.filter.raster(image, ("swaprb", "brightness:2"))

        self.assertEqual(filtered.getpixel((0, 0)), (60, 40, 20, 255))

    def test_legacy_wkt_drawing_without_color_parameter(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "request": "GetMap",
                "layers": "transparent",
                "format": "image/png",
                "width": "32",
                "height": "32",
                "bbox": "-1,-1,1,1",
                "wkt": "LINESTRING(-1 -1,1 1)",
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/png")
        with Image.open(BytesIO(body)) as image:
            self.assertEqual(image.size, (32, 32))
            self.assertTrue(
                any(image.getchannel("A").tobytes()),
                "WKT overlay should draw visible pixels",
            )

    def test_legacy_canvas_blank_tile_smoke(self):
        canvas = twms.canvas.WmsCanvas(tile_size=(32, 32))

        canvas.FetchTile(0, 0)

        self.assertEqual(canvas.tiles[(0, 0)]["im"].size, (32, 32))
        self.assertEqual(canvas.tiles[(0, 0)]["im"].mode, "RGBA")

    def test_legacy_canvas_uses_default_upstream_timeout(self):
        canvas = twms.canvas.WmsCanvas(
            wms_url="http://example.test/wms?",
            proj="EPSG:3857",
        )

        with mock.patch("twms.canvas.urlopen") as urlopen:
            urlopen.return_value.read.return_value = self.image_bytes((1, 2, 3, 255))
            canvas.FetchTile(0, 0)

        urlopen.assert_called_once_with(mock.ANY, timeout=30)

    def test_legacy_canvas_can_preserve_unbounded_upstream_wait(self):
        canvas = twms.canvas.WmsCanvas(
            wms_url="http://example.test/wms?",
            proj="EPSG:3857",
            timeout=None,
        )

        with mock.patch("twms.canvas.urlopen") as urlopen:
            urlopen.return_value.read.return_value = self.image_bytes((1, 2, 3, 255))
            canvas.FetchTile(0, 0)

        urlopen.assert_called_once_with(mock.ANY, timeout=None)

    def test_getimg_resize_works_with_current_pillow(self):
        tile = Image.new("RGBA", (256, 256), (1, 2, 3, 255))
        tile.is_ok = True
        layer = {
            "name": "Resize smoke",
            "prefix": "resize",
            "proj": "EPSG:3857",
            "cached": False,
            "max_zoom": 1,
        }

        with mock.patch("twms.twms.tile_image", return_value=tile):
            image = twms.twms.getimg(
                (-1.0, -1.0, 1.0, 1.0),
                "EPSG:3857",
                (32, 32),
                layer,
                datetime.datetime.now(),
                (),
            )

        self.assertEqual(image.size, (32, 32))
        self.assertEqual(image.getpixel((0, 0)), (1, 2, 3, 255))

    def test_legacy_empty_color_overlay_is_transparent(self):
        base = Image.new("RGBA", (2, 1), (10, 20, 30, 255))
        overlay = Image.new("RGBA", (2, 1), (255, 255, 255, 255))
        overlay.putpixel((1, 0), (255, 0, 0, 255))
        base.is_ok = True
        overlay.is_ok = True
        layers = {
            "base": {"empty_color": "#000000"},
            "overlay": {"empty_color": "#ffffff"},
        }

        with mock.patch.object(twms.twms.config, "layers", layers):
            with mock.patch.object(twms.twms, "getimg", side_effect=[base, overlay]):
                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetMap",
                        "layers": "base,overlay",
                        "format": "image/png",
                        "bbox": "0,0,1,1",
                        "width": "2",
                        "height": "1",
                    }
                )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/png")
        with Image.open(BytesIO(body)) as image:
            image = image.convert("RGBA")
            self.assertEqual(image.getpixel((0, 0)), (10, 20, 30, 255))
            self.assertEqual(image.getpixel((1, 0)), (132, 10, 15, 255))

    def test_legacy_empty_color_delta_applies_per_channel(self):
        base = Image.new("RGBA", (1, 1), (10, 20, 30, 255))
        overlay = Image.new("RGBA", (1, 1), (255, 254, 253, 255))
        base.is_ok = True
        overlay.is_ok = True
        layers = {
            "base": {"empty_color": "#000000"},
            "overlay": {
                "empty_color": "#ffffff",
                "empty_color_delta": 2,
            },
        }

        with mock.patch.object(twms.twms.config, "layers", layers):
            with mock.patch.object(twms.twms, "getimg", side_effect=[base, overlay]):
                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetMap",
                        "layers": "base,overlay",
                        "format": "image/png",
                        "bbox": "0,0,1,1",
                        "width": "1",
                        "height": "1",
                    }
                )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/png")
        with Image.open(BytesIO(body)) as image:
            self.assertEqual(image.convert("RGBA").getpixel((0, 0)), (10, 20, 30, 255))

    def test_tilejson_smoke(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "request": "GetTileJSON",
                "layers": "osm",
                "ref": "http://example.test/",
            }
        )

        doc = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(doc["tilejson"], "3.0.0")
        self.assertEqual(doc["name"], "OpenStreetMap mapnik")
        self.assertEqual(doc["scheme"], "xyz")
        self.assertEqual(doc["tiles"], ["http://example.test/osm/{z}/{x}/{y}.png"])
        self.assertEqual(doc["bounds"], [-180.0, -85.0511287798, 180.0, 85.0511287798])
        self.assertEqual(doc["minzoom"], 0)
        self.assertEqual(doc["maxzoom"], 18)

    def test_josm_imagery_xml_smoke(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "request": "GetJOSMImagery",
                "ref": "http://example.test/",
            }
        )

        namespaces = {"josm": "http://josm.openstreetmap.de/maps-1.0"}
        root = ET.fromstring(body)
        osm = root.find("./josm:entry[josm:id='twms-osm']", namespaces)
        landsat = root.find("./josm:entry[josm:id='twms-landsat']", namespaces)

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/xml")
        self.assertEqual(root.tag, "{http://josm.openstreetmap.de/maps-1.0}imagery")
        self.assertEqual(osm.find("josm:name", namespaces).text, "OpenStreetMap mapnik")
        self.assertEqual(osm.find("josm:type", namespaces).text, "tms")
        self.assertEqual(
            osm.find("josm:url", namespaces).text,
            "http://example.test/osm/{zoom}/{x}/{y}.png",
        )
        self.assertEqual(landsat.find("josm:max-zoom", namespaces).text, "11")

    def test_wmts_capabilities_smoke(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "service": "WMTS",
                "request": "GetCapabilities",
                "ref": "http://example.test/",
            }
        )

        root = ET.fromstring(body)
        namespaces = {
            "wmts": "http://www.opengis.net/wmts/1.0",
            "ows": "http://www.opengis.net/ows/1.1",
        }
        layer_ids = [
            element.text
            for element in root.findall(
                "./wmts:Contents/wmts:Layer/ows:Identifier",
                namespaces,
            )
        ]
        resource = root.find(
            "./wmts:Contents/wmts:Layer[ows:Identifier='osm']/wmts:ResourceURL",
            namespaces,
        )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/xml")
        self.assertEqual(root.tag, "{http://www.opengis.net/wmts/1.0}Capabilities")
        self.assertIn("osm", layer_ids)
        self.assertEqual(
            resource.attrib["template"],
            "http://example.test/wmts/osm/{TileMatrix}/{TileCol}/{TileRow}.png",
        )

    def test_wmts_kvp_gettile_smoke(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "service": "WMTS",
                "request": "GetTile",
                "layer": "transparent",
                "format": "image/png",
                "tilematrix": "0",
                "tilecol": "0",
                "tilerow": "0",
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/png")
        with Image.open(BytesIO(body)) as image:
            self.assertEqual(image.size, (256, 256))
            self.assertEqual(image.mode, "RGBA")

    def test_webmercator_projection_clamps_poles(self):
        maxbounds = 6378137 * math.pi

        projected = twms.projections.from4326(
            (-180.0, -90.0, 180.0, 90.0),
            "EPSG:3857",
        )

        self.assertEqual(projected[0], -maxbounds)
        self.assertEqual(projected[1], -maxbounds)
        self.assertEqual(projected[2], maxbounds)
        self.assertEqual(projected[3], maxbounds)

    def test_optional_pyproj_projection_uses_modern_transformer(self):
        if not hasattr(twms.projections.pyproj, "Transformer"):
            self.skipTest("pyproj extra is not installed")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            point = twms.projections.from4326((27.6, 53.2), "EPSG:32635")

        self.assertTrue(540000 < point[0] < 541000)
        self.assertTrue(5894000 < point[1] < 5895000)
        self.assertFalse(
            [warning for warning in caught if warning.category is FutureWarning],
        )

    def test_non_core_projection_reports_missing_pyproj_extra(self):
        if hasattr(twms.projections.pyproj, "Transformer"):
            self.skipTest("pyproj extra is installed")

        with self.assertRaises(NotImplementedError) as raised:
            twms.projections.from4326((27.6, 53.2), "EPSG:32635")

        self.assertIn("twms[proj]", str(raised.exception))

    def test_tile_cache_uses_fresh_file_without_network(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "ttl",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "cache_ttl": 3600,
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                os.makedirs(os.path.dirname(path))
                with open(path, "wb") as cached_tile:
                    cached_tile.write(self.image_bytes((10, 20, 30, 255)))

                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                urlopen.assert_not_called()
                self.assertEqual(image.getpixel((0, 0)), (10, 20, 30, 255))
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_tile_cache_can_use_zxy_layout(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "zxy",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "cache_layout": "zxy",
            }
            try:
                path = self.zxy_cache_path(cache_root, layer, 2, 3, 4)
                legacy_path = self.cache_path(cache_root, layer, 2, 3, 4)
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (10, 20, 30, 255)
                    )
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                self.assertEqual(image.getpixel((0, 0)), (10, 20, 30, 255))
                self.assertTrue(os.path.exists(path))
                self.assertFalse(os.path.exists(legacy_path))
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_tile_cache_can_reuse_fresh_zxy_file_without_network(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "zxy-hit",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "cache_layout": "zxy",
                "cache_ttl": 3600,
            }
            try:
                path = self.zxy_cache_path(cache_root, layer, 2, 3, 4)
                os.makedirs(os.path.dirname(path))
                with open(path, "wb") as tile_file:
                    tile_file.write(self.image_bytes((70, 80, 90, 255)))

                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                self.assertEqual(image.getpixel((0, 0)), (70, 80, 90, 255))
                urlopen.assert_not_called()
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_tile_cache_refetches_expired_file_and_keeps_stale_on_error(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "ttl",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "cache_ttl": 1,
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                os.makedirs(os.path.dirname(path))
                with open(path, "wb") as cached_tile:
                    cached_tile.write(self.image_bytes((10, 20, 30, 255)))
                old_time = 946684800
                os.utime(path, (old_time, old_time))

                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (40, 50, 60, 255)
                    )
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                urlopen.assert_called_once()
                self.assertEqual(image.getpixel((0, 0)), (40, 50, 60, 255))

                os.utime(path, (old_time, old_time))
                with mock.patch("twms.fetchers.urlopen", side_effect=OSError):
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                self.assertEqual(image.getpixel((0, 0)), (40, 50, 60, 255))
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_tile_cache_tne_suppresses_fetch_until_ttl_expires(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "ttl",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "cache_ttl": 3600,
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                tne_path = path[:-3] + "tne"
                os.makedirs(os.path.dirname(tne_path))
                open(tne_path, "wb").close()

                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                urlopen.assert_not_called()
                self.assertIsNone(image)
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_dead_tile_dict_is_recorded_as_tne(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            body = self.image_bytes((255, 0, 0, 255))
            layer = {
                "prefix": "dead",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "dead_tile": {
                    "size": len(body),
                    "md5": {hashlib.md5(body).hexdigest()},
                },
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                tne_path = path[:-3] + "tne"
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = body
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                self.assertFalse(image)
                self.assertFalse(os.path.exists(path))
                self.assertTrue(os.path.exists(tne_path))
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_invalid_downloaded_tile_is_not_cached(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "invalid",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = b"not an image"
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                self.assertFalse(image)
                self.assertFalse(os.path.exists(path))
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_tile_cache_converts_download_to_layer_extension(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "format",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.jpg",
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (20, 30, 40), image_format="JPEG"
                    )
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                self.assertEqual(image.format, "JPEG")
                with Image.open(path) as cached_image:
                    self.assertEqual(cached_image.format, "PNG")
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_http_404_tile_is_recorded_as_tne(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "http-tne",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                tne_path = path[:-3] + "tne"
                error = urllib.error.HTTPError(
                    "http://example.test/2/3/4.png",
                    404,
                    "Not Found",
                    hdrs={},
                    fp=None,
                )
                with mock.patch("twms.fetchers.urlopen", side_effect=error):
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                self.assertFalse(image)
                self.assertFalse(os.path.exists(path))
                self.assertTrue(os.path.exists(tne_path))
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_wms_fetcher_caches_downloaded_image(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "wms-cache",
                "ext": "png",
                "remote_url": "http://example.test/wms?",
                "proj": "EPSG:3857",
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (1, 2, 3, 255)
                    )
                    image = twms.fetchers.WMS(2, 3, 4, layer)

                self.assertEqual(image.getpixel((0, 0)), (1, 2, 3, 255))
                self.assertTrue(os.path.exists(path))
                urlopen.assert_called_once_with(mock.ANY, timeout=30)
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_wms_fetcher_keeps_legacy_url_append(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "wms-legacy-url",
                "ext": "png",
                "remote_url": "http://example.test/wms?",
                "proj": "EPSG:3857",
            }
            try:
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (1, 2, 3, 255)
                    )
                    twms.fetchers.WMS(2, 3, 4, layer)

                url = urlopen.call_args.args[0]
                self.assertIsInstance(url, str)
                self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)
                self.assertTrue(url.startswith("http://example.test/wms?bbox="))
                self.assertIn("&width=384&height=384&srs=EPSG:3857", url)
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_wms_fetcher_formats_named_url_placeholders(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "wms-template-url",
                "ext": "png",
                "remote_url": (
                    "http://example.test/wms?SERVICE=WMS&REQUEST=GetMap"
                    "&WIDTH={width}&HEIGHT={height}&CRS={proj}&BBOX={bbox}"
                ),
                "proj": "EPSG:3857",
            }
            try:
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (1, 2, 3, 255)
                    )
                    twms.fetchers.WMS(2, 3, 4, layer)

                url = urlopen.call_args.args[0]
                self.assertIsInstance(url, str)
                self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)
                self.assertIn("WIDTH=384&HEIGHT=384&CRS=EPSG:3857&BBOX=", url)
                self.assertNotIn("srs=EPSG:3857", url)
                self.assertEqual(url.count("BBOX="), 1)
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_tile_fetcher_respects_min_zoom(self):
        layer = {
            "prefix": "minzoom",
            "ext": "png",
            "remote_url": "http://example.test/%s/%s/%s.png",
            "min_zoom": 3,
        }

        with mock.patch("twms.fetchers.urlopen") as urlopen:
            image = twms.fetchers.Tile(2, 3, 4, layer)

        self.assertIsNone(image)
        urlopen.assert_not_called()

    def test_wms_fetcher_respects_min_zoom(self):
        layer = {
            "prefix": "wms-minzoom",
            "ext": "png",
            "remote_url": "http://example.test/wms?",
            "proj": "EPSG:3857",
            "min_zoom": 3,
        }

        with mock.patch("twms.fetchers.urlopen") as urlopen:
            image = twms.fetchers.WMS(2, 3, 4, layer)

        self.assertIsNone(image)
        urlopen.assert_not_called()

    def test_tile_fetcher_keeps_legacy_exclusive_max_zoom(self):
        layer = {
            "prefix": "maxzoom",
            "ext": "png",
            "remote_url": "http://example.test/%s/%s/%s.png",
            "max_zoom": 2,
        }

        with mock.patch("twms.fetchers.urlopen") as urlopen:
            image = twms.fetchers.Tile(2, 3, 4, layer)

        self.assertIsNone(image)
        urlopen.assert_not_called()

    def test_tile_fetcher_sends_configured_headers(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "headers",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "headers": {
                    "Referer": "https://example.test/map/",
                    "User-Agent": "twms-test",
                },
            }
            try:
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (1, 2, 3, 255)
                    )
                    twms.fetchers.Tile(2, 3, 4, layer)

                request = urlopen.call_args.args[0]
                headers = {
                    key.lower(): value for key, value in request.header_items()
                }
                self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)
                self.assertEqual(request.full_url, "http://example.test/2/3/4.png")
                self.assertEqual(headers["referer"], "https://example.test/map/")
                self.assertEqual(headers["user-agent"], "twms-test")
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_wms_fetcher_sends_configured_headers(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "wms-headers",
                "ext": "png",
                "remote_url": "http://example.test/wms?",
                "proj": "EPSG:3857",
                "headers": {
                    "Referer": "https://example.test/wms-client/",
                },
            }
            try:
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (1, 2, 3, 255)
                    )
                    twms.fetchers.WMS(2, 3, 4, layer)

                request = urlopen.call_args.args[0]
                headers = {
                    key.lower(): value for key, value in request.header_items()
                }
                self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)
                self.assertTrue(request.full_url.startswith("http://example.test/wms?"))
                self.assertIn("bbox=", request.full_url)
                self.assertEqual(headers["referer"], "https://example.test/wms-client/")
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_tile_fetcher_uses_configured_layer_timeout(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "timeout",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "timeout": 7,
            }
            try:
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (1, 2, 3, 255)
                    )
                    twms.fetchers.Tile(2, 3, 4, layer)

                urlopen.assert_called_once_with(
                    "http://example.test/2/3/4.png",
                    timeout=7,
                )
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_configured_http_status_tile_is_recorded_as_tne(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "http-tne",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "dead_tile": {"http_status": 410},
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                tne_path = path[:-3] + "tne"
                error = urllib.error.HTTPError(
                    "http://example.test/2/3/4.png",
                    410,
                    "Gone",
                    hdrs={},
                    fp=None,
                )
                with mock.patch("twms.fetchers.urlopen", side_effect=error):
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                self.assertFalse(image)
                self.assertFalse(os.path.exists(path))
                self.assertTrue(os.path.exists(tne_path))
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_legacy_percent_tile_template_still_uses_transform_tuple(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "url",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "transform_tile_number": lambda z, x, y: (x, y, z - 1),
            }
            try:
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (1, 2, 3, 255)
                    )
                    twms.fetchers.Tile(2, 3, 4, layer)

                urlopen.assert_called_once_with(
                    "http://example.test/3/4/1.png",
                    timeout=30,
                )
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_named_tile_template_placeholders(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "url",
                "ext": "png",
                "remote_url": "http://example.test/{z}/{x}/{y}/{-y}/{q}.png",
            }
            try:
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (1, 2, 3, 255)
                    )
                    twms.fetchers.Tile(4, 9, 5, layer)

                urlopen.assert_called_once_with(
                    "http://example.test/4/9/5/10/1203.png",
                    timeout=30,
                )
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_named_tile_template_uses_transform_tuple(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "url",
                "ext": "png",
                "remote_url": "http://example.test/z{z}/x{x}/y{y}.png",
                "transform_tile_number": lambda z, x, y: (z - 1, x + 1, y + 2),
            }
            try:
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = self.image_bytes(
                        (1, 2, 3, 255)
                    )
                    twms.fetchers.Tile(4, 5, 6, layer)

                urlopen.assert_called_once_with(
                    "http://example.test/z3/x6/y8.png",
                    timeout=30,
                )
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_wsgi_application_imports(self):
        self.assertTrue(callable(twms.daemon.application))

    def test_stdlib_server_serves_wms_and_gettile(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), twms.server.TWMSRequestHandler)
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        base = "http://127.0.0.1:%s" % httpd.server_address[1]
        try:
            with urllib.request.urlopen(
                base + "/?request=GetCapabilities&version=1.1.1"
            ) as response:
                body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("application/vnd.ogc.wms_xml", response.headers["Content-Type"])
                self.assertIn("<WMT_MS_Capabilities", body)

            with urllib.request.urlopen(base + "/transparent/0/0/0.png") as response:
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn("image/png", response.headers["Content-Type"])
                with Image.open(BytesIO(body)) as image:
                    self.assertEqual(image.size, (256, 256))
                    self.assertEqual(image.mode, "RGBA")

            with urllib.request.urlopen(base + "/tilejson/osm.json") as response:
                doc = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 200)
                self.assertIn("application/json", response.headers["Content-Type"])
                self.assertEqual(doc["tiles"], [base + "/osm/{z}/{x}/{y}.png"])

            with urllib.request.urlopen(base + "/josm/imagery.xml") as response:
                root = ET.fromstring(response.read().decode("utf-8"))
                namespaces = {"josm": "http://josm.openstreetmap.de/maps-1.0"}
                osm = root.find("./josm:entry[josm:id='twms-osm']", namespaces)
                self.assertEqual(response.status, 200)
                self.assertIn("text/xml", response.headers["Content-Type"])
                self.assertEqual(
                    osm.find("josm:url", namespaces).text,
                    base + "/osm/{zoom}/{x}/{y}.png",
                )

            with urllib.request.urlopen(
                base + "/wmts/1.0.0/WMTSCapabilities.xml"
            ) as response:
                root = ET.fromstring(response.read().decode("utf-8"))
                self.assertEqual(response.status, 200)
                self.assertIn("text/xml", response.headers["Content-Type"])
                self.assertEqual(
                    root.tag,
                    "{http://www.opengis.net/wmts/1.0}Capabilities",
                )

            with urllib.request.urlopen(base + "/wmts/transparent/0/0/0.png") as response:
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn("image/png", response.headers["Content-Type"])
                with Image.open(BytesIO(body)) as image:
                    self.assertEqual(image.size, (256, 256))
                    self.assertEqual(image.mode, "RGBA")

            with urllib.request.urlopen(
                base + "/wmts/transparent/0/0/0.png?cache=1"
            ) as response:
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn("image/png", response.headers["Content-Type"])
                with Image.open(BytesIO(body)) as image:
                    self.assertEqual(image.size, (256, 256))
                    self.assertEqual(image.mode, "RGBA")

            for path in ("/wmts", "/tilejson/.json", "/does-not-exist"):
                with self.subTest(path=path):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(base + path)
                    self.assertEqual(error.exception.code, 404)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
