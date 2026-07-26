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
import urllib.request
import warnings
from http.server import ThreadingHTTPServer
import xml.etree.ElementTree as ET
from unittest import mock

from PIL import Image

import twms
import twms.daemon
import twms.fetchers
import twms.projections
import twms.server
import twms.twms


class LegacySmokeTest(unittest.TestCase):
    def image_bytes(self, color, image_format="PNG"):
        buffer = BytesIO()
        Image.new("RGBA", (256, 256), color).save(buffer, image_format)
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
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
