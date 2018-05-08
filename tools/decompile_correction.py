# -*- coding: utf-8 -*-
from __future__ import print_function

import sys

tiles_cache = "/var/www/latlon/wms/cache/"
layers = ["irs", "yhsat", "DGsat", "yasat"]

out = sys.stdout

for lay in layers:
    nid, wid = 1, 1
    out = open(lay+".osm","w")
    corrfile = tiles_cache + lay+ "/rectify.txt"
    corr = open(corrfile, "r")
    print('<osm version="0.6">', file=out)
    for line in corr:
       d,c,b,a,user,ts = line.split()
       d,c,b,a = (float(d),float(c),float(b),float(a))
       print('<node id="-%s" lon="%s" lat="%s" version="1" />'%(nid, d, c), file=out)
       nid += 1
       print('<node id="-%s" lon="%s" lat="%s" version="1" />'%(nid, b, a), file=out)
       nid += 1
       print('<way id="-%s" version="1">'%(wid), file=out)
       print(' <nd ref="-%s" />'%(nid-2), file=out)
       print(' <nd ref="-%s" />'%(nid-1), file=out)
       print(' <tag k="%s" v="%s" />"'%("user", user), file=out)
       print(' <tag k="%s" v="%s" />"'%("timestamp", ts), file=out)
       print("</way>", file=out)
       wid += 1
    print('</osm>', file=out)
