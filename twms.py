#!/usr/bin/python
# -*- coding: utf-8 -*-
#    This file is part of tWMS.

#   tWMS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.

#   tWMS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with tWMS.  If not, see <http://www.gnu.org/licenses/>.

import web
import sys
from twms.twms import *

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
        return handler(data)



if __name__ == "__main__":
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

