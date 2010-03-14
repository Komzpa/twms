# -*- coding: utf-8 -*-
import sys

tiles_cache = "/var/www/latlon/wms/cache/"
layers = ["irs", "yhsat", "DGsat", "yasat"]

out = sys.stdout

for lay in layers:
    nid, wid = 1, 1
    out = open(lay+".osm","w")
    corrfile = tiles_cache + lay+ "/rectify.txt"
    corr = open(corrfile, "r")
    print >> out, '<osm version="0.6">'
    for line in corr:
       d,c,b,a,user,ts = line.split()
       d,c,b,a = (float(d),float(c),float(b),float(a))
       print >> out, '<node id="-%s" lon="%s" lat="%s" version="1" />'%(nid, d, c)
       nid += 1
       print >> out, '<node id="-%s" lon="%s" lat="%s" version="1" />'%(nid, b, a)
       nid += 1
       print >> out, '<way id="-%s" version="1">'%(wid)
       print >> out,' <nd ref="-%s" />'%(nid-2)
       print >> out,' <nd ref="-%s" />'%(nid-1)
       print >> out,' <tag k="%s" v="%s" />"'%("user", user)
       print >> out,' <tag k="%s" v="%s" />"'%("timestamp", ts)
       print >> out,"</way>"
       wid += 1
    print >> out, '</osm>'