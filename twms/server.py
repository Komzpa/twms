#!/usr/bin/python3
# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from twms import twms_main


tile_route = re.compile(r"/(.*)/([0-9]+)/([0-9]+)/([0-9]+)(\.[a-zA-Z]+)?(.*)")
wms_tile_route = re.compile(
    r"/wms/([^/]+)/([0-9]+)/([0-9]+)/([0-9]+)(\.[a-zA-Z]+)?"
)
tilejson_route = re.compile(r"/tilejson/(.+)\.json")
josm_imagery_routes = {"/josm/imagery.xml", "/josm/maps.xml", "/maps.xml"}
wmts_capabilities_route = "/wmts/1.0.0/WMTSCapabilities.xml"
wmts_tile_route = re.compile(
    r"/wmts/([^/]+)/([0-9]+)/([0-9]+)/([0-9]+)(\.[a-zA-Z]+)?"
)


def request_url(handler):
    scheme = "http"
    host = handler.headers.get("Host")
    if not host:
        host = "%s:%s" % handler.server.server_address[:2]
    return "%s://%s/" % (scheme, host)


def _tile_data(match):
    ext = match.group(5) or ".jpg"
    return {
        "request": "GetTile",
        "layers": match.group(1),
        "format": ext.strip(".").lower(),
        "z": match.group(2),
        "x": match.group(3),
        "y": match.group(4),
    }


def dispatch(path, ref=None):
    parsed = urllib.parse.urlsplit(path)
    tilejson_match = tilejson_route.fullmatch(parsed.path)
    if tilejson_match:
        data = {
            "request": "GetTileJSON",
            "layers": urllib.parse.unquote(tilejson_match.group(1)),
        }
    elif parsed.path in josm_imagery_routes:
        data = {
            "request": "GetJOSMImagery",
        }
    elif parsed.path == wmts_capabilities_route:
        data = {
            "request": "GetCapabilities",
            "service": "WMTS",
        }
    else:
        match = wms_tile_route.fullmatch(parsed.path)
        if match:
            data = _tile_data(match)
        else:
            match = wmts_tile_route.fullmatch(parsed.path)
            if match:
                data = _tile_data(match)
            else:
                match = tile_route.fullmatch(parsed.path)
                if match:
                    data = _tile_data(match)
                else:
                    if not parsed.query and parsed.path not in ("", "/", "/wms"):
                        return 404, "text/plain", "Not Found\n"
                    data = dict(urllib.parse.parse_qsl(parsed.query))
                    data = dict((key.lower(), data[key]) for key in data)
                    if ref and parsed.path == "/wms":
                        ref = urllib.parse.urljoin(ref, "wms")

    if ref and "ref" not in data:
        data["ref"] = ref
    return twms_main(data)


class TWMSRequestHandler(BaseHTTPRequestHandler):
    server_version = "twms"

    def do_GET(self):
        status, content_type, content = dispatch(self.path, request_url(self))
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if "text/" in content_type or "xml" in content_type:
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self.end_headers()
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.wfile.write(content)

    def log_message(self, format, *args):
        pass


def main():
    try:
        port = int(sys.argv[1])
    except IndexError:
        port = 8080

    server = ThreadingHTTPServer(("", port), TWMSRequestHandler)
    print("TWMS server listening on port %s" % port)
    server.serve_forever()


if __name__ == "__main__":
    main()
