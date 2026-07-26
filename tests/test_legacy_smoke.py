import importlib
import importlib.metadata
import json
from io import BytesIO
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
import xml.etree.ElementTree as ET

from PIL import Image

import twms
import twms.daemon
import twms.server
import twms.twms


class LegacySmokeTest(unittest.TestCase):
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
