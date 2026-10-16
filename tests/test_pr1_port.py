from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen
from io import BytesIO
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch

from PIL import Image
from twms import __main__, api, config, fetchers, projections, twms


class PortedPRFeaturesTest(unittest.TestCase):
    def test_wms_130_capabilities_and_crs84_alias(self):
        status, content_type, response = twms.TWMSMain().wms_handler(
            {"request": "getcapabilities", "version": "1.3.0"}
        )
        root = ET.fromstring(response)
        self.assertEqual(status.value, 200)
        self.assertEqual(content_type, "text/xml")
        self.assertEqual(root.attrib["version"], "1.3.0")
        self.assertEqual(
            root.findtext(".//{http://www.opengis.net/wms}CRS"), "CRS:84"
        )
        self.assertEqual(
            projections.transform((12.0, 34.0), projections.EPSG("CRS:84"), projections.EPSG("EPSG:4326")),
            (12.0, 34.0),
        )

    def test_tilejson_request(self):
        layer_id = next(iter(config.layers))
        status, content_type, response = twms.TWMSMain().wms_handler(
            {"request": "GetTileJSON", "layers": layer_id}
        )
        metadata = json.loads(response)
        self.assertEqual(status.value, 200)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(metadata["tilejson"], "3.0.0")
        self.assertEqual(metadata["scheme"], "xyz")
        self.assertIn(f"/wms/{layer_id}/{{z}}/{{x}}/{{y}}", metadata["tiles"][0])
        self.assertEqual(api.tilejson_document(layer_id)["bounds"], list(config.layers[layer_id]["bounds"]))

    def test_tilejson_http_route(self):
        layer_id = next(iter(config.layers))
        with ThreadingHTTPServer(("127.0.0.1", 0), __main__.GetHandler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(
                    f"http://127.0.0.1:{server.server_port}/tilejson/{layer_id}.json"
                ) as response:
                    metadata = json.loads(response.read())
                self.assertEqual(metadata["tilejson"], "3.0.0")
            finally:
                server.shutdown()
                thread.join()

    def test_empty_color_tolerance_makes_overlay_pixel_transparent(self):
        client = twms.TWMSMain()
        client.bbox_image = Mock(
            side_effect=[
                Image.new("RGBA", (1, 1), (0, 0, 255, 255)),
                Image.new("RGBA", (1, 1), (101, 0, 0, 255)),
            ]
        )
        layers = {
            "base": {},
            "overlay": {"empty_color": "#640000", "empty_color_delta": 1},
        }
        with patch.dict(config.layers, layers):
            status, content_type, image_bytes = client.wms_handler(
                {
                    "layers": "base,overlay",
                    "format": "image/png",
                    "width": "1",
                    "height": "1",
                }
            )
        self.assertEqual(status.value, 200)
        self.assertEqual(content_type, "image/png")
        with Image.open(BytesIO(image_bytes)) as rendered:
            self.assertEqual(rendered.getpixel((0, 0)), (0, 0, 255, 255))

    def test_tile_cache_replacement_is_atomic(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            tile = fetchers.TileFile(cache_dir, "layer", "image/png", 1, 2, 3)
            tile.path.parent.mkdir(parents=True)
            tile.path.write_bytes(b"old")
            with patch("twms.fetchers.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    tile.set(b"new")
            self.assertEqual(tile.path.read_bytes(), b"old")
            self.assertEqual(list(tile.path.parent.iterdir()), [tile.path])

    def test_upstream_request_has_a_finite_default_timeout(self):
        session = fetchers.HttpSessionDirector(timeout=1.5)
        session.opener_director.open = Mock(return_value="response")
        self.assertEqual(session.get("https://example.invalid/tile"), "response")
        session.opener_director.open.assert_called_once_with(
            "https://example.invalid/tile", timeout=1.5
        )


if __name__ == "__main__":
    unittest.main()
