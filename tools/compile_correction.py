#!/usr/bin/python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
from lxml import etree

tiles_cache = "/var/www/latlon/wms/cache/"
layers = ["irs", "yhsat", "DGsat", "yasat", "SAT"]
default_user = "Komzpa"
user = default_user
ts = ""

corr = sys.stdout
nodes = {}
curway = []
for lay in layers:
    print(lay)
    src = lay + ".osm"
    if os.path.exists(src):
        corrfile = tiles_cache + lay + "/rectify.txt"
        corr = open(corrfile, "w")
        context = etree.iterparse(open(src))
        for action, elem in context:
            items = dict(elem.items())
            ts = items.get("timestamp", ts)

            #   print items
            if elem.tag == "node":
                nodes[int(items["id"])] = (float(items["lon"]), float(items["lat"]))
            elif elem.tag == "nd":
                curway.append(nodes[int(items["ref"])])
            elif elem.tag == "tag":
                if items["k"] == "user":
                    user = items["v"]
                if items["k"] == "timestamp":
                    ts = items["v"]
            elif elem.tag == "way":
                ts = items.get("timestamp", ts)
                print(
                    "%s %s %s %s %s %s"
                    % (
                        curway[0][0],
                        curway[0][1],
                        curway[1][0],
                        curway[1][1],
                        user,
                        ts,
                    ),
                    file=corr,
                )
                curway = []
                user = default_user
                ts = ""
