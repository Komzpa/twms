#!/usr/bin/env python

import logging
import mimetypes
import os
import re
import textwrap
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import twms
import twms.api
import twms.config
import twms.twms

mimetypes.init()  # Init or mimetypes.types_map['.webp'] wont work
# https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
logging.addLevelName(
    logging.WARNING, "\x1b[33;20m%s\033[1;0m" % logging.getLevelName(logging.WARNING)
)
logging.addLevelName(
    logging.ERROR, "\033[1;41m%s\033[1;0m" % logging.getLevelName(logging.ERROR)
)

"""
 0 NOTSET
10 DEBUG - tile file operations
20 INFO - tile fetching or construction
30 WARNING warning - HTTP errors
40 ERROR and `exception()` Logs Traceback and Stack with `exc_info=exc_info`
50 CRITICAL `and fatal()`

Debug trace shall contain:
  * Origin link (with headers, probably)
  * TWMS link
  * File cache link
"""
logging.basicConfig(level=logging.INFO)
# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class GetHandler(BaseHTTPRequestHandler):
    TWMS = twms.twms.TWMSMain()
    server_version = f"twms/{twms.__version__}"
    wms_route = re.compile(r"/wms/(.*)/(\d+)/(\d+)/(\d+)(\.[a-zA-Z]+)?(.*)")

    def do_GET(self):
        """Handle GET request.

        wms/layer_id/{z}/{x}/{y}{ext}
        tiles/layer_id/{z}/{x}/{y}
        josm/maps.xml
        any overview
        """
        if self.path.startswith("/tilejson/"):
            match = re.fullmatch(
                r"/tilejson/(.+)\.json", urllib.parse.urlsplit(self.path).path
            )
            if match:
                data = {
                    "request": "GetTileJSON",
                    "layers": urllib.parse.unquote(match.group(1)),
                }
                status, content_type, content = self.TWMS.wms_handler(data)
            else:
                status = HTTPStatus.NOT_FOUND
                content_type = "text/plain"
                content = repr(status)
        elif self.path.startswith("/wmts"):
            if self.path.startswith("/wmts/1.0.0/WMTSCapabilities.xml"):
                status = HTTPStatus.OK
                content_type = "text/xml"
                content = twms.api.maps_wmts_rest()
            else:
                root, ext = os.path.splitext(self.path)
                r_parts = root.split("/")
                layer_id, z, x, y = r_parts[2], r_parts[3], r_parts[4], r_parts[5]
                status, content_type, content = self.TWMS.tiles_handler(
                    layer_id, z, x, y, mimetypes.types_map[ext]
                )

        elif self.path.startswith("/wms"):
            # WMS and somewhat like WMS-C emulation for getting tiles directly
            wms_c = self.wms_route.fullmatch(self.path)
            if wms_c:
                # Construct WMS-like request
                # Guess image format by link extension
                data = {
                    "request": "GetTile",
                    "layers": wms_c.group(1),
                    "format": mimetypes.types_map.get(wms_c.group(5), None),
                    "z": wms_c.group(2),  # Not a part of the WMS spec
                    "x": wms_c.group(3),
                    "y": wms_c.group(4),
                }
                # rest = m.group(6)
            else:
                data = dict(urllib.parse.parse_qsl(self.path.split("?")[1]))
            status, content_type, content = self.TWMS.wms_handler(data)

        elif self.path == "/josm/maps.xml":
            status = HTTPStatus.OK
            content_type = "text/xml"
            content = twms.api.maps_xml_josm()
        elif self.path == "/":
            status = HTTPStatus.OK
            content_type = "text/html"
            content = twms.api.maps_html()
        else:
            status = HTTPStatus.NOT_FOUND
            content_type = "text/plain"
            content = repr(status)

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if "text/" in content_type or "xml" in content_type or "json" in content_type:
            # JOSM tends to save old XML
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")  # HTTP 1.0
            self.send_header("Expires", "0")  # Proxy
        self.end_headers()
        if "text/" in content_type or "xml" in content_type or "json" in content_type:
            content = content.encode("utf-8")
        self.wfile.write(content)

    def log_message(self, format, *args):
        """Override logger."""
        logger.info(format, *args)

    def log_error(self, format, *args):
        """Override logger."""
        logger.error(format, *args)


def main():
    """Run simple TWMS server."""
    server = ThreadingHTTPServer((twms.config.host, twms.config.port), GetHandler)
    print(
        textwrap.dedent(
            f"""\
        TWMS server {twms.__version__}
        {twms.config.service_url} imagery overview web page
        {twms.config.service_wms_url}?SERVICE=WMS&REQUEST=GetCapabilities
        {twms.config.service_wmts_url}/1.0.0/WMTSCapabilities.xml
        {twms.config.service_url}/josm/maps.xml Add this to JOSM 'imagery.layers.sites' property and check imagery setting"
        Edit `twms/config.py` for new layers and custom settings.
        Press <Ctrl-C> to stop"""
        )
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
