import importlib
import importlib.metadata
from io import BytesIO
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

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
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
