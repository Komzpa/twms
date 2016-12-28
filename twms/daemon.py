#!/usr/bin/python
# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://www.wtfpl.net/ for more details.

import web
import sys
from twms import *

import sys, socket

try:
        import psyco
        psyco.full()
except ImportError:
        pass

OK = 200
ERROR = 500


def handler(data):
    """
    A handler for web.py.
    """
    resp, ctype, content = twms_main(data)
    web.header('Content-Type', ctype)
    return content



urls = (
      '/(.*)/([0-9]+)/([0-9]+)/([0-9]+)(\.[a-zA-Z]+)?(.*)', 'tilehandler',
      '/(.*)', 'mainhandler'
)

class tilehandler:
    def GET(self, layers, z, x, y, format, rest):
        if format is None:
            format = "jpeg"
        else:
            format = format.lower()
        data = {
            "request": "GetTile",
            "layers": layers,
            "format": format.strip("."),
            "z": z,
            "x": x,
            "y": y
        }
        return handler(data)


class mainhandler:
    def GET(self, crap):
        data = web.input()
        data = dict((k.lower(), v) for k, v in data.iteritems())
        if "ref" not in data:
            if web.ctx.env['HTTP_HOST']:
                data["ref"] = web.ctx.env['wsgi.url_scheme'] + "://" + web.ctx.env['HTTP_HOST'] + "/"
        return handler(data)



def main():
    try:
     if sys.argv[1] == "josm":                                  # josm mode 
      import cgi
      url, params = sys.argv[2].split("/?", 1)
      data = cgi.parse_qs(params)
      for t in data.keys():
        data[t] = data[t][0]
      resp, ctype, content = twms_main(data)
      print content
      exit()
    except IndexError:
      pass

    try:
      app = web.application(urls, globals())
      app.run()                                                  # standalone run
    except socket.error:
      print "Can't open socket. Abort."
      sys.exit(1)


application = web.application(urls, globals()).wsgifunc()        # mod_wsgi

if __name__ == "__main__":
    main()
