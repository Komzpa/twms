import datetime
import importlib
import importlib.metadata
import contextlib
import hashlib
import json
import math
import os
from collections import OrderedDict
from io import BytesIO, StringIO
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
import twms.config_loader
import twms.correctify
import twms.daemon
import twms.fetchers
import twms.filter
import twms.gpxparse
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

    def rendered_point_centroid(self, body):
        image = Image.open(BytesIO(body)).convert("RGBA")
        pixels = []
        for y in range(image.height):
            for x in range(image.width):
                red, green, blue, alpha = image.getpixel((x, y))
                if alpha and green > red and green > blue:
                    pixels.append((x, y))
        self.assertTrue(pixels, "expected a visible WKT point")
        return (
            sum(x for x, _ in pixels) / len(pixels),
            sum(y for _, y in pixels) / len(pixels),
        )

    def cache_path(self, cache_root, layer, z, x, y):
        return os.path.join(
            cache_root,
            layer["prefix"],
            "z%s" % z,
            "%s" % (x // 1024),
            "x%s" % x,
            "%s" % (y // 1024),
            "y%s.%s" % (y, twms.fetchers._layer_extension(layer)),
        )

    def zxy_cache_path(self, cache_root, layer, z, x, y):
        return os.path.join(
            cache_root,
            layer["prefix"],
            "%s" % z,
            "%s" % x,
            "%s.%s" % (y, twms.fetchers._layer_extension(layer)),
        )

    def test_public_version_keeps_keyboard_suffix(self):
        self.assertEqual(twms.__version__, "0.07z")
        self.assertEqual(importlib.metadata.version("twms"), "0.7+z")

    def test_layer_metadata_normalizes_ext_and_mimetype(self):
        module = type("Config", (), {})()
        module.default_format = "image/png"
        module.layers = {
            "mimetype-only": {"mimetype": "image/png"},
            "ext-only": {"ext": "jpg"},
            "default-format": {},
        }

        twms.config_loader.normalize_layer_metadata(module)

        self.assertEqual(module.layers["mimetype-only"]["ext"], "png")
        self.assertEqual(module.layers["ext-only"]["mimetype"], "image/jpeg")
        self.assertEqual(module.layers["default-format"]["mimetype"], "image/png")
        self.assertEqual(module.layers["default-format"]["ext"], "png")

    def test_layer_metadata_supports_layer_defaults(self):
        module = type("Config", (), {})()
        module.layer_defaults = {
            "mimetype": "image/png",
            "proj": "EPSG:3857",
            "cached": False,
        }
        module.layers = {
            "defaulted": {"name": "Defaulted", "prefix": "defaulted"},
            "override": {"name": "Override", "prefix": "override", "ext": "jpg"},
        }

        twms.config_loader.normalize_layer_metadata(module)

        defaulted = module.layers["defaulted"]
        override = module.layers["override"]
        self.assertNotIn("ext", defaulted)
        self.assertEqual(defaulted["proj"], "EPSG:3857")
        self.assertEqual(defaulted.get("mimetype"), "image/png")
        self.assertEqual(defaulted.get("ext"), "png")
        self.assertEqual(defaulted.get("cached"), False)
        self.assertEqual(override["proj"], "EPSG:3857")
        self.assertEqual(override.get("mimetype"), "image/jpeg")
        self.assertEqual(override.get("ext"), "jpg")

    def test_layer_metadata_accepts_string_fetch_aliases(self):
        module = type("Config", (), {})()
        module.layers = {
            "tiles": {"fetch": "tms"},
            "wms": {"fetch": "wms"},
        }

        twms.config_loader.normalize_layer_metadata(module)

        self.assertIs(module.layers["tiles"]["fetch"], twms.fetchers.Tile)
        self.assertIs(module.layers["wms"]["fetch"], twms.fetchers.WMS)

    def test_layer_metadata_accepts_default_string_fetch_alias(self):
        module = type("Config", (), {})()
        module.layer_defaults = {"fetch": "wms"}
        module.layers = {
            "defaulted": {"name": "Defaulted", "prefix": "defaulted"},
        }

        twms.config_loader.normalize_layer_metadata(module)

        self.assertIs(module.layers["defaulted"]["fetch"], twms.fetchers.WMS)

    def test_layer_metadata_rejects_unknown_string_fetch_alias(self):
        module = type("Config", (), {})()
        module.layers = {"bad": {"fetch": "factory-factory"}}

        with self.assertRaisesRegex(ValueError, "factory-factory"):
            twms.config_loader.normalize_layer_metadata(module)

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
        self.assertIn("<Format>image/webp</Format>", body)
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

    def test_wms_getmap_accepts_webp_format(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "request": "GetMap",
                "layers": "transparent",
                "format": "image/webp",
                "width": "32",
                "height": "32",
                "srs": "EPSG:3857",
                "bbox": "-1,-1,1,1",
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/webp")
        with Image.open(BytesIO(body)) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertEqual(image.size, (32, 32))

    def test_overview_smoke(self):
        status, content_type, body = twms.twms.twms_main({"ref": "http://example.test/"})

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/html")
        self.assertIn("<table>", body)
        self.assertIn("Yandex Satellite", body)

    def test_overview_accepts_bounds_alias_and_provider_link(self):
        old_config_layers = twms.twms.config.layers
        old_overview_layers = twms.twms.overview.layers
        layers = {
            "bounded": {
                "name": "Bounded",
                "prefix": "bounded",
                "ext": "png",
                "proj": "EPSG:3857",
                "bounds": (1.0, 2.0, 3.0, 4.0),
                "provider_url": "http://provider.example/",
            }
        }
        twms.twms.config.layers = layers
        twms.twms.overview.layers = layers
        try:
            status, content_type, body = twms.twms.twms_main(
                {"ref": "http://example.test/"}
            )

            self.assertEqual(status, 200)
            self.assertEqual(content_type, "text/html")
            self.assertIn("bbox=1.0,2.0,3.0,4.0", body)
            self.assertIn(
                '<a referrerpolicy="no-referrer" href="http://provider.example/">'
                "Bounded</a>",
                body,
            )
        finally:
            twms.twms.config.layers = old_config_layers
            twms.twms.overview.layers = old_overview_layers

    def test_overview_accepts_mimetype_only_layer(self):
        old_config_layers = twms.twms.config.layers
        old_overview_layers = twms.twms.overview.layers
        layers = {
            "typed": {
                "name": "Typed",
                "prefix": "typed",
                "mimetype": "image/png",
                "proj": "EPSG:3857",
            }
        }
        twms.twms.config.layers = layers
        twms.twms.overview.layers = layers
        try:
            status, content_type, body = twms.twms.twms_main(
                {"ref": "http://example.test/"}
            )

            self.assertEqual(status, 200)
            self.assertEqual(content_type, "text/html")
            self.assertIn("http://example.test/typed/!/!/!.png", body)
        finally:
            twms.twms.config.layers = old_config_layers
            twms.twms.overview.layers = old_overview_layers

    def test_overview_accepts_layer_defaults(self):
        old_config_layers = twms.twms.config.layers
        old_overview_layers = twms.twms.overview.layers
        module = type("Config", (), {})()
        module.layer_defaults = {"mimetype": "image/png", "proj": "EPSG:3857"}
        module.layers = {"defaulted": {"name": "Defaulted", "prefix": "defaulted"}}
        twms.config_loader.normalize_layer_metadata(module)
        twms.twms.config.layers = module.layers
        twms.twms.overview.layers = module.layers
        try:
            status, content_type, body = twms.twms.twms_main(
                {"ref": "http://example.test/"}
            )

            self.assertEqual(status, 200)
            self.assertEqual(content_type, "text/html")
            self.assertIn("http://example.test/defaulted/!/!/!.png", body)
        finally:
            twms.twms.config.layers = old_config_layers
            twms.twms.overview.layers = old_overview_layers

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

    def test_legacy_gpx_track_points_keep_parse_order_on_python3(self):
        with tempfile.NamedTemporaryFile("w", suffix=".gpx", delete=False) as gpx_file:
            gpx_path = gpx_file.name
            gpx_file.write(
                """<?xml version="1.0"?>
                <gpx version="1.1" creator="twms-test">
                  <trk><trkseg>
                    <trkpt lat="53.1" lon="27.1"><time>2026-01-01T00:00:00Z</time></trkpt>
                    <trkpt lat="53.2" lon="27.2"><time>2026-01-01T00:01:00Z</time></trkpt>
                  </trkseg></trk>
                </gpx>
                """
            )
        try:
            track = twms.gpxparse.GPXParser(gpx_path)
        finally:
            os.unlink(gpx_path)

        self.assertEqual(track.bbox, (27.1, 53.1, 27.2, 53.2))
        self.assertEqual(track.getTrack(0), [(27.1, 53.1), (27.2, 53.2)])

    def test_legacy_gpx_trace_download_uses_python3_urlretrieve(self):
        gpx_body = b"""<?xml version="1.0"?>
        <gpx version="1.1" creator="twms-test">
          <trk><trkseg>
            <trkpt lat="53.1" lon="27.1"><time>2026-01-01T00:00:00Z</time></trkpt>
            <trkpt lat="53.2" lon="27.2"><time>2026-01-01T00:01:00Z</time></trkpt>
          </trkseg></trk>
        </gpx>
        """

        def write_gpx(url, filename):
            self.assertEqual(url, "http://www.openstreetmap.org/trace/123/data")
            with open(filename, "wb") as trace_file:
                trace_file.write(gpx_body)

        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.twms.config.gpx_cache
            twms.twms.config.gpx_cache = cache_root + os.sep
            try:
                with mock.patch("twms.twms.urlretrieve", side_effect=write_gpx):
                    status, content_type, body = twms.twms.twms_main(
                        {
                            "request": "GetMap",
                            "layers": "transparent",
                            "format": "image/png",
                            "width": "16",
                            "height": "16",
                            "gpx": "123",
                        }
                    )

                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                self.assertIsInstance(body, bytes)
                self.assertTrue(os.path.exists(os.path.join(cache_root, "123.gpx")))
            finally:
                twms.twms.config.gpx_cache = old_cache

    def test_legacy_filter_smoke(self):
        image = Image.new("RGBA", (2, 1), (10, 20, 30, 255))

        filtered = twms.filter.raster(image, ("swaprb", "brightness:2"))

        self.assertEqual(filtered.getpixel((0, 0)), (60, 40, 20, 255))

    @unittest.skipUnless(twms.filter.NUMPY_AVAILABLE, "numpy not installed")
    def test_legacy_fusion_filter_is_quiet_and_uses_original_intensity(self):
        image = Image.new("RGBA", (2, 1))
        image.putdata([(10, 20, 30, 255), (0, 0, 0, 255)])
        pan = Image.new("L", (2, 1))
        pan.putdata([60, 60])
        old_layers = twms.filter.config.layers
        twms.filter.config.layers = {"pan": {"name": "Pan"}}
        stdout = StringIO()
        try:
            with mock.patch("twms.filter.getimg", return_value=pan):
                with contextlib.redirect_stdout(stdout):
                    filtered = twms.filter.raster(image, ("fusion:pan",))
        finally:
            twms.filter.config.layers = old_layers

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(filtered.getpixel((0, 0)), (10, 20, 30, 255))
        self.assertEqual(filtered.getpixel((1, 0)), (0, 0, 0, 255))

    def test_legacy_rectify_returns_projection_bounds_without_identity_trick(self):
        bounds = twms.projections.projs["EPSG:3857"]["bounds"]
        min_point = (float(str(bounds[0])), float(str(bounds[1])))
        layer = {"prefix": "bounded", "proj": "EPSG:3857"}

        with tempfile.TemporaryDirectory() as cache_root:
            layer_root = os.path.join(cache_root, "bounded")
            os.makedirs(layer_root)
            with open(os.path.join(layer_root, "rectify.txt"), "w") as corr_file:
                corr_file.write("27.0 53.0 27.1 53.1 user 2026-01-01T00:00:00Z\n")
            old_cache = twms.correctify.config.tiles_cache
            twms.correctify.config.tiles_cache = cache_root + os.sep
            try:
                self.assertEqual(twms.correctify.rectify(layer, min_point), min_point)
            finally:
                twms.correctify.config.tiles_cache = old_cache

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

    def test_wkt_point_position_follows_request_bbox(self):
        examples = [
            ("-83,-41.8,67,68.8", (396, 140)),
            ("-83,11.8,67,68.8", (396, 272)),
        ]
        for bbox, expected in examples:
            with self.subTest(bbox=bbox):
                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetMap",
                        "layers": "transparent",
                        "format": "image/png",
                        "width": "800",
                        "height": "600",
                        "bbox": bbox,
                        "wkt": "POINT(-8.55 42.85)",
                    }
                )

                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                centroid = self.rendered_point_centroid(body)
                self.assertAlmostEqual(centroid[0], expected[0], delta=1)
                self.assertAlmostEqual(centroid[1], expected[1], delta=1)

    def test_noresize_without_width_or_height_uses_tile_size(self):
        status, content_type, body = twms.twms.twms_main(
            {
                "request": "GetMap",
                "layers": "transparent",
                "format": "image/png",
                "bbox": "-1,-1,1,1",
                "force": "noresize",
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "image/png")
        with Image.open(BytesIO(body)) as image:
            self.assertEqual(image.size, (256, 256))

    def test_legacy_canvas_blank_tile_smoke(self):
        canvas = twms.canvas.WmsCanvas(tile_size=(32, 32))

        canvas.FetchTile(0, 0)

        self.assertEqual(canvas.tiles[(0, 0)]["im"].size, (32, 32))
        self.assertEqual(canvas.tiles[(0, 0)]["im"].mode, "RGBA")

    def test_legacy_canvas_prepare_pixel_initializes_tile_once(self):
        canvas = twms.canvas.WmsCanvas(tile_size=(32, 32))

        canvas.PreparePixel(33, 65)

        if "thread" in canvas.tiles[(1, 2)]:
            canvas.tiles[(1, 2)]["thread"].join()
        self.assertEqual(canvas.tiles[(1, 2)]["status"], "RD")
        self.assertEqual(canvas.tiles[(1, 2)]["im"].size, (32, 32))

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
        self.assertEqual(doc["maxzoom"], 17)

    def test_tilejson_maxzoom_is_last_requestable_zoom(self):
        old_layers = twms.twms.config.layers
        twms.twms.config.layers = {
            "exclusive": {
                "name": "Exclusive",
                "prefix": "exclusive",
                "ext": "png",
                "proj": "EPSG:3857",
                "max_zoom": 7,
            }
        }
        try:
            status, content_type, body = twms.twms.twms_main(
                {
                    "request": "GetTileJSON",
                    "layers": "exclusive",
                    "ref": "http://example.test/",
                }
            )

            doc = json.loads(body)
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/json")
            self.assertEqual(doc["maxzoom"], 6)
        finally:
            twms.twms.config.layers = old_layers

    def test_tilejson_accepts_layer_bounds_alias(self):
        old_layers = twms.twms.config.layers
        twms.twms.config.layers = {
            "bounded": {
                "name": "Bounded",
                "prefix": "bounded",
                "ext": "png",
                "proj": "EPSG:3857",
                "bounds": (1.0, 2.0, 3.0, 4.0),
            }
        }
        try:
            status, content_type, body = twms.twms.twms_main(
                {
                    "request": "GetTileJSON",
                    "layers": "bounded",
                    "ref": "http://example.test/",
                }
            )

            doc = json.loads(body)
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/json")
            self.assertEqual(doc["bounds"], [1.0, 2.0, 3.0, 4.0])
            self.assertEqual(doc["center"], [2.0, 3.0, 0])
        finally:
            twms.twms.config.layers = old_layers

    def test_tilejson_accepts_mimetype_only_layer(self):
        old_layers = twms.twms.config.layers
        twms.twms.config.layers = {
            "typed": {
                "name": "Typed",
                "prefix": "typed",
                "mimetype": "image/png",
                "proj": "EPSG:3857",
            }
        }
        try:
            status, content_type, body = twms.twms.twms_main(
                {
                    "request": "GetTileJSON",
                    "layers": "typed",
                    "ref": "http://example.test/",
                }
            )

            doc = json.loads(body)
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/json")
            self.assertEqual(doc["tiles"], ["http://example.test/typed/{z}/{x}/{y}.png"])
        finally:
            twms.twms.config.layers = old_layers

    def test_tilejson_accepts_layer_defaults(self):
        old_layers = twms.twms.config.layers
        module = type("Config", (), {})()
        module.layer_defaults = {"mimetype": "image/png", "proj": "EPSG:3857"}
        module.layers = {"defaulted": {"name": "Defaulted", "prefix": "defaulted"}}
        twms.config_loader.normalize_layer_metadata(module)
        twms.twms.config.layers = module.layers
        try:
            status, content_type, body = twms.twms.twms_main(
                {
                    "request": "GetTileJSON",
                    "layers": "defaulted",
                    "ref": "http://example.test/",
                }
            )

            doc = json.loads(body)
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/json")
            self.assertEqual(
                doc["tiles"], ["http://example.test/defaulted/{z}/{x}/{y}.png"]
            )
        finally:
            twms.twms.config.layers = old_layers

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
        self.assertEqual(osm.find("josm:default", namespaces).text, "true")
        self.assertEqual(osm.find("josm:name", namespaces).text, "OpenStreetMap mapnik")
        self.assertEqual(osm.find("josm:type", namespaces).text, "tms")
        self.assertEqual(
            osm.find("josm:url", namespaces).text,
            "http://example.test/osm/{zoom}/{x}/{y}.png",
        )
        self.assertEqual(
            osm.find("josm:description", namespaces).text,
            "OpenStreetMap mapnik",
        )
        self.assertEqual(osm.find("josm:valid-georeference", namespaces).text, "true")
        self.assertEqual(landsat.find("josm:max-zoom", namespaces).text, "11")

    def test_josm_imagery_xml_accepts_mimetype_only_layer(self):
        old_layers = twms.twms.config.layers
        twms.twms.config.layers = {
            "typed": {
                "name": "Typed",
                "prefix": "typed",
                "mimetype": "image/png",
                "proj": "EPSG:3857",
            }
        }
        try:
            status, content_type, body = twms.twms.twms_main(
                {
                    "request": "GetJOSMImagery",
                    "ref": "http://example.test/",
                }
            )

            namespaces = {"josm": "http://josm.openstreetmap.de/maps-1.0"}
            root = ET.fromstring(body)
            entry = root.find("./josm:entry[josm:id='twms-typed']", namespaces)

            self.assertEqual(status, 200)
            self.assertEqual(content_type, "text/xml")
            self.assertEqual(
                entry.find("josm:url", namespaces).text,
                "http://example.test/typed/{zoom}/{x}/{y}.png",
            )
        finally:
            twms.twms.config.layers = old_layers

    def test_josm_imagery_xml_layer_metadata(self):
        old_layers = twms.twms.config.layers
        twms.twms.config.layers = {
            "metadata": {
                "name": "Metadata",
                "prefix": "metadata",
                "ext": "png",
                "proj": "EPSG:3857",
                "bounds": (1.0, 2.0, 3.0, 4.0),
                "overlay": True,
                "provider_url": "http://provider.example/",
                "dead_tile": {
                    "md5": {
                        "11111111111111111111111111111111",
                        "22222222222222222222222222222222",
                    },
                },
                "min_zoom": 3,
                "max_zoom": 7,
            }
        }
        try:
            status, content_type, body = twms.twms.twms_main(
                {
                    "request": "GetJOSMImagery",
                    "ref": "http://example.test/",
                }
            )

            namespaces = {"josm": "http://josm.openstreetmap.de/maps-1.0"}
            root = ET.fromstring(body)
            entry = root.find("./josm:entry[josm:id='twms-metadata']", namespaces)
            bounds = entry.find("josm:bounds", namespaces)
            checksums = entry.findall("josm:no-tile-checksum", namespaces)

            self.assertEqual(status, 200)
            self.assertEqual(content_type, "text/xml")
            self.assertEqual(entry.attrib["overlay"], "true")
            self.assertEqual(
                entry.find("josm:attribution-url", namespaces).text,
                "http://provider.example/",
            )
            self.assertEqual(
                bounds.attrib,
                {
                    "min-lon": "1.0",
                    "min-lat": "2.0",
                    "max-lon": "3.0",
                    "max-lat": "4.0",
                },
            )
            self.assertEqual(
                [(item.attrib["type"], item.attrib["value"]) for item in checksums],
                [
                    ("MD5", "11111111111111111111111111111111"),
                    ("MD5", "22222222222222222222222222222222"),
                ],
            )
            self.assertEqual(entry.find("josm:min-zoom", namespaces).text, "3")
            self.assertEqual(entry.find("josm:max-zoom", namespaces).text, "6")
        finally:
            twms.twms.config.layers = old_layers

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

    def test_wmts_capabilities_accepts_layer_bounds_alias(self):
        old_layers = twms.twms.config.layers
        twms.twms.config.layers = {
            "bounded": {
                "name": "Bounded",
                "prefix": "bounded",
                "ext": "png",
                "proj": "EPSG:3857",
                "bounds": (1.0, 2.0, 3.0, 4.0),
            }
        }
        try:
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
            bounds = root.find(
                "./wmts:Contents/wmts:Layer[ows:Identifier='bounded']/ows:WGS84BoundingBox",
                namespaces,
            )

            self.assertEqual(status, 200)
            self.assertEqual(content_type, "text/xml")
            self.assertEqual(bounds.find("ows:LowerCorner", namespaces).text, "1.0 2.0")
            self.assertEqual(bounds.find("ows:UpperCorner", namespaces).text, "3.0 4.0")
        finally:
            twms.twms.config.layers = old_layers

    def test_wmts_capabilities_accepts_mimetype_only_layer(self):
        old_layers = twms.twms.config.layers
        twms.twms.config.layers = {
            "typed": {
                "name": "Typed",
                "prefix": "typed",
                "mimetype": "image/png",
                "proj": "EPSG:3857",
            }
        }
        try:
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
            layer = root.find(
                "./wmts:Contents/wmts:Layer[ows:Identifier='typed']",
                namespaces,
            )
            resource = layer.find("wmts:ResourceURL", namespaces)
            format_node = layer.find("wmts:Format", namespaces)

            self.assertEqual(status, 200)
            self.assertEqual(content_type, "text/xml")
            self.assertEqual(resource.attrib["format"], "image/png")
            self.assertEqual(
                resource.attrib["template"],
                "http://example.test/wmts/typed/{TileMatrix}/{TileCol}/{TileRow}.png",
            )
            self.assertEqual(format_node.text, "image/png")
        finally:
            twms.twms.config.layers = old_layers

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

    def test_pure_projection_roundtrips_match_legacy_smoke_point(self):
        lon_lat = (27.6, 53.2)

        for srs in ("EPSG:3857", "EPSG:3395"):
            projected = twms.projections.from4326(lon_lat, srs)
            roundtripped = twms.projections.to4326(projected, srs)

            self.assertAlmostEqual(roundtripped[0], lon_lat[0], places=6)
            self.assertAlmostEqual(roundtripped[1], lon_lat[1], places=6)

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

    def test_legacy_tile_image_reuses_historical_cache_path(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.twms.config.tiles_cache
            twms.twms.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "legacy-hit",
                "proj": "EPSG:3857",
                "ext": "png",
                "cached": True,
                "scalable": False,
                "empty_color": "#000000",
                "fetch": mock.Mock(return_value=None),
            }
            try:
                path = self.cache_path(cache_root, layer, 3, 3, 3)
                os.makedirs(os.path.dirname(path))
                with open(path, "wb") as cached_tile:
                    cached_tile.write(self.image_bytes((10, 20, 30, 255)))

                image = twms.twms.tile_image(
                    layer,
                    3,
                    3,
                    3,
                    datetime.datetime.now(),
                    real=True,
                )

                layer["fetch"].assert_not_called()
                self.assertEqual(image.getpixel((0, 0)), (10, 20, 30, 255))
            finally:
                twms.twms.config.tiles_cache = old_cache

    def test_legacy_ram_cache_is_lru_bounded(self):
        old_cached_objs = twms.twms.cached_objs
        old_limit = twms.twms.config.max_ram_cached_tiles
        twms.twms.cached_objs = OrderedDict()
        twms.twms.config.max_ram_cached_tiles = 2
        layer = {"prefix": "ram"}
        first = Image.new("RGBA", (1, 1), (1, 1, 1, 255))
        second = Image.new("RGBA", (1, 1), (2, 2, 2, 255))
        third = Image.new("RGBA", (1, 1), (3, 3, 3, 255))
        try:
            first_key = twms.twms._ram_cache_key(layer, 1, 1, 1)
            second_key = twms.twms._ram_cache_key(layer, 1, 2, 2)
            third_key = twms.twms._ram_cache_key(layer, 1, 3, 3)
            twms.twms._ram_cache_put(first_key, first)
            twms.twms._ram_cache_put(second_key, second)

            self.assertIs(twms.twms._ram_cache_get(first_key), first)

            twms.twms._ram_cache_put(third_key, third)

            self.assertIn(first_key, twms.twms.cached_objs)
            self.assertNotIn(second_key, twms.twms.cached_objs)
            self.assertIn(third_key, twms.twms.cached_objs)
        finally:
            twms.twms.cached_objs = old_cached_objs
            twms.twms.config.max_ram_cached_tiles = old_limit

    def test_legacy_gettile_fast_cache_reads_binary_tile(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.twms.config.tiles_cache
            old_layers = twms.twms.config.layers
            twms.twms.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "legacy-fast-hit",
                "proj": "EPSG:3857",
                "ext": "png",
            }
            twms.twms.config.layers = {"legacy-fast-hit": layer}
            try:
                path = self.cache_path(cache_root, layer, 3, 3, 4)
                os.makedirs(os.path.dirname(path))
                with open(path, "wb") as cached_tile:
                    cached_tile.write(self.image_bytes((10, 20, 30, 255)))

                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetTile",
                        "layers": "legacy-fast-hit",
                        "format": "image/png",
                        "z": "2",
                        "x": "3",
                        "y": "4",
                    }
                )

                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                self.assertIsInstance(body, bytes)
                with Image.open(BytesIO(body)) as image:
                    self.assertEqual(image.getpixel((0, 0)), (10, 20, 30, 255))
            finally:
                twms.twms.config.tiles_cache = old_cache
                twms.twms.config.layers = old_layers

    def test_legacy_response_cache_reads_binary_tile(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = getattr(twms.twms.config, "cache_tile_responses", None)
            had_cache = hasattr(twms.twms.config, "cache_tile_responses")
            twms.twms.config.cache_tile_responses = {
                ("EPSG:3857", ("transparent",), (), 256, 256, (), "PNG"): (
                    cache_root,
                    "png",
                ),
            }
            try:
                path = os.path.join(cache_root, "2", "3", "4.png")
                os.makedirs(os.path.dirname(path))
                with open(path, "wb") as cached_tile:
                    cached_tile.write(self.image_bytes((10, 20, 30, 255)))

                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetTile",
                        "layers": "transparent",
                        "format": "image/png",
                        "z": "2",
                        "x": "3",
                        "y": "4",
                    }
                )

                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                self.assertIsInstance(body, bytes)
                with Image.open(BytesIO(body)) as image:
                    self.assertEqual(image.getpixel((0, 0)), (10, 20, 30, 255))
            finally:
                if had_cache:
                    twms.twms.config.cache_tile_responses = old_cache
                else:
                    del twms.twms.config.cache_tile_responses

    def test_legacy_response_cache_accepts_mime_format_key(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = getattr(twms.twms.config, "cache_tile_responses", None)
            had_cache = hasattr(twms.twms.config, "cache_tile_responses")
            twms.twms.config.cache_tile_responses = {
                ("EPSG:3857", ("transparent",), (), 256, 256, (), "image/png"): (
                    cache_root,
                    "png",
                ),
            }
            try:
                path = os.path.join(cache_root, "2", "3", "4.png")
                os.makedirs(os.path.dirname(path))
                with open(path, "wb") as cached_tile:
                    cached_tile.write(self.image_bytes((12, 34, 56, 255)))

                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetTile",
                        "layers": "transparent",
                        "format": "image/png",
                        "z": "2",
                        "x": "3",
                        "y": "4",
                    }
                )

                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                self.assertIsInstance(body, bytes)
                with Image.open(BytesIO(body)) as image:
                    self.assertEqual(image.getpixel((0, 0)), (12, 34, 56, 255))
            finally:
                if had_cache:
                    twms.twms.config.cache_tile_responses = old_cache
                else:
                    del twms.twms.config.cache_tile_responses

    def test_empty_filter_and_force_match_response_cache_keys(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = getattr(twms.twms.config, "cache_tile_responses", None)
            had_cache = hasattr(twms.twms.config, "cache_tile_responses")
            twms.twms.config.cache_tile_responses = {
                ("EPSG:3857", ("transparent",), (), 256, 256, (), "PNG"): (
                    cache_root,
                    "png",
                ),
            }
            try:
                path = os.path.join(cache_root, "2", "3", "4.png")
                os.makedirs(os.path.dirname(path))
                expected = self.image_bytes((80, 90, 100, 255))
                with open(path, "wb") as cached_tile:
                    cached_tile.write(expected)

                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetTile",
                        "layers": "transparent",
                        "format": "image/png",
                        "z": "2",
                        "x": "3",
                        "y": "4",
                        "filter": "",
                        "force": "",
                    }
                )

                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                self.assertEqual(body, expected)
            finally:
                if had_cache:
                    twms.twms.config.cache_tile_responses = old_cache
                else:
                    del twms.twms.config.cache_tile_responses

    def test_filter_alias_matches_response_cache_keys(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = getattr(twms.twms.config, "cache_tile_responses", None)
            had_cache = hasattr(twms.twms.config, "cache_tile_responses")
            twms.twms.config.cache_tile_responses = {
                ("EPSG:3857", ("transparent",), ("bw",), 256, 256, (), "PNG"): (
                    cache_root,
                    "png",
                ),
            }
            try:
                path = os.path.join(cache_root, "2", "3", "4.png")
                os.makedirs(os.path.dirname(path))
                expected = self.image_bytes((82, 92, 102, 255))
                with open(path, "wb") as cached_tile:
                    cached_tile.write(expected)

                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetTile",
                        "layers": "transparent",
                        "format": "image/png",
                        "z": "2",
                        "x": "3",
                        "y": "4",
                        "filter": "bw",
                    }
                )

                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                self.assertEqual(body, expected)
            finally:
                if had_cache:
                    twms.twms.config.cache_tile_responses = old_cache
                else:
                    del twms.twms.config.cache_tile_responses

    def test_legacy_response_cache_writes_binary_tile(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = getattr(twms.twms.config, "cache_tile_responses", None)
            had_cache = hasattr(twms.twms.config, "cache_tile_responses")
            twms.twms.config.cache_tile_responses = {
                ("EPSG:3857", ("transparent",), (), 256, 256, (), "PNG"): (
                    cache_root,
                    "png",
                ),
            }
            try:
                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetTile",
                        "layers": "transparent",
                        "format": "image/png",
                        "z": "2",
                        "x": "3",
                        "y": "4",
                    }
                )

                path = os.path.join(cache_root, "2", "3", "4.png")
                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                self.assertIsInstance(body, bytes)
                with open(path, "rb") as cached_tile:
                    self.assertEqual(cached_tile.read(), body)
                with Image.open(path) as image:
                    self.assertEqual(image.size, (256, 256))
            finally:
                if had_cache:
                    twms.twms.config.cache_tile_responses = old_cache
                else:
                    del twms.twms.config.cache_tile_responses

    def test_legacy_response_cache_writes_mime_format_key(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = getattr(twms.twms.config, "cache_tile_responses", None)
            had_cache = hasattr(twms.twms.config, "cache_tile_responses")
            twms.twms.config.cache_tile_responses = {
                ("EPSG:3857", ("transparent",), (), 256, 256, (), "image/png"): (
                    cache_root,
                    "png",
                ),
            }
            try:
                status, content_type, body = twms.twms.twms_main(
                    {
                        "request": "GetTile",
                        "layers": "transparent",
                        "format": "image/png",
                        "z": "2",
                        "x": "3",
                        "y": "4",
                    }
                )

                path = os.path.join(cache_root, "2", "3", "4.png")
                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                self.assertIsInstance(body, bytes)
                with open(path, "rb") as cached_tile:
                    self.assertEqual(cached_tile.read(), body)
                with Image.open(path) as image:
                    self.assertEqual(image.size, (256, 256))
            finally:
                if had_cache:
                    twms.twms.config.cache_tile_responses = old_cache
                else:
                    del twms.twms.config.cache_tile_responses

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

    def test_tile_fetch_retries_transient_upstream_error(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "retry",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "upstream_retries": 2,
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                response = mock.Mock()
                response.read.return_value = self.image_bytes((11, 22, 33, 255))
                with mock.patch(
                    "twms.fetchers.urlopen",
                    side_effect=[OSError("temporary"), response],
                ) as urlopen:
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                self.assertEqual(urlopen.call_count, 2)
                self.assertEqual(image.getpixel((0, 0)), (11, 22, 33, 255))
                self.assertTrue(os.path.exists(path))
            finally:
                twms.fetchers.config.tiles_cache = old_cache

    def test_tile_fetch_does_not_retry_http_tne_status(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "retry-http-tne",
                "ext": "png",
                "remote_url": "http://example.test/%s/%s/%s.png",
                "upstream_retries": 3,
            }
            try:
                path = self.cache_path(cache_root, layer, 2, 3, 4)
                tne_path = path[:-3] + "tne"
                error = urllib.error.HTTPError(
                    url="http://example.test/2/3/4.png",
                    code=404,
                    msg="Not Found",
                    hdrs={},
                    fp=None,
                )
                with mock.patch("twms.fetchers.urlopen", side_effect=error) as urlopen:
                    image = twms.fetchers.Tile(2, 3, 4, layer)

                urlopen.assert_called_once()
                self.assertFalse(image)
                self.assertTrue(os.path.exists(tne_path))
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

    def test_direct_gettile_first_fetch_returns_cached_upstream_bytes(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_twms_cache = twms.twms.config.tiles_cache
            old_fetchers_cache = twms.fetchers.config.tiles_cache
            old_layers = twms.twms.config.layers
            twms.twms.config.tiles_cache = cache_root + os.sep
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "raw-first-fetch",
                "proj": "EPSG:3857",
                "ext": "png",
                "scalable": False,
                "fetch": twms.fetchers.Tile,
                "remote_url": "http://example.test/%s/%s/%s.png",
                "transform_tile_number": lambda z, x, y: (z - 1, x, y),
            }
            twms.twms.config.layers = {"raw-first-fetch": layer}
            upstream_bytes = self.image_bytes((10, 20, 30, 255)) + b"raw-marker"
            try:
                path = self.cache_path(cache_root, layer, 3, 3, 3)
                with mock.patch("twms.fetchers.urlopen") as urlopen:
                    urlopen.return_value.read.return_value = upstream_bytes
                    status, content_type, body = twms.twms.twms_main(
                        {
                            "request": "GetTile",
                            "layers": "raw-first-fetch",
                            "format": "image/png",
                            "z": "2",
                            "x": "3",
                            "y": "3",
                        }
                    )

                self.assertEqual(status, 200)
                self.assertEqual(content_type, "image/png")
                self.assertEqual(body, upstream_bytes)
                with open(path, "rb") as cached_tile:
                    self.assertEqual(cached_tile.read(), upstream_bytes)
            finally:
                twms.twms.config.tiles_cache = old_twms_cache
                twms.fetchers.config.tiles_cache = old_fetchers_cache
                twms.twms.config.layers = old_layers

    def test_tile_cache_accepts_mimetype_only_layer(self):
        with tempfile.TemporaryDirectory() as cache_root:
            old_cache = twms.fetchers.config.tiles_cache
            twms.fetchers.config.tiles_cache = cache_root + os.sep
            layer = {
                "prefix": "mimetype",
                "mimetype": "image/png",
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
                self.assertTrue(path.endswith(".png"))
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

    def test_legacy_tile_image_accepts_layer_bounds_alias(self):
        layer = {
            "prefix": "bounded",
            "ext": "png",
            "proj": "EPSG:3857",
            "bounds": (170.0, -80.0, 171.0, -79.0),
            "scalable": False,
            "fetch": twms.fetchers.Tile,
            "remote_url": "http://example.test/%s/%s/%s.png",
        }

        with mock.patch("twms.fetchers.fetch") as fetch:
            image = twms.twms.tile_image(
                layer,
                2,
                0,
                0,
                datetime.datetime.now(),
            )

        self.assertIsNone(image)
        fetch.assert_not_called()

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

    def test_stdlib_server_startup_banner_lists_client_urls(self):
        banner = twms.server.startup_banner("", 8080)

        self.assertIn("TWMS server 0.07z listening on 0.0.0.0:8080", banner)
        self.assertIn("Overview: http://127.0.0.1:8080/", banner)
        self.assertIn(
            "WMS: http://127.0.0.1:8080/wms?SERVICE=WMS&REQUEST=GetCapabilities",
            banner,
        )
        self.assertIn(
            "WMTS: http://127.0.0.1:8080/wmts/1.0.0/WMTSCapabilities.xml",
            banner,
        )
        self.assertIn("JOSM imagery: http://127.0.0.1:8080/josm/maps.xml", banner)
        self.assertNotIn("Cookie", banner)
        self.assertNotIn("headers", banner.lower())

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
                self.assertIn("twms/0.07z", response.headers["Server"])
                self.assertIn("application/vnd.ogc.wms_xml", response.headers["Content-Type"])
                self.assertIn("<WMT_MS_Capabilities", body)

            with urllib.request.urlopen(
                base + "/wms?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.1.1"
            ) as response:
                body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("application/vnd.ogc.wms_xml", response.headers["Content-Type"])
                self.assertIn('xlink:href="' + base + '/wms?"', body)

            with urllib.request.urlopen(base + "/transparent/0/0/0.png") as response:
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn("image/png", response.headers["Content-Type"])
                with Image.open(BytesIO(body)) as image:
                    self.assertEqual(image.size, (256, 256))
                    self.assertEqual(image.mode, "RGBA")

            with urllib.request.urlopen(base + "/wms/transparent/0/0/0.png") as response:
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

            with urllib.request.urlopen(base + "/josm/maps.xml") as response:
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
