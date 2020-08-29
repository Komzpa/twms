# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

import sys, string, bz2, gzip, os
from xml.dom import minidom, Node


class GPXParser:
    def __init__(self, filename):
        self.tracks = {}
        self.pointnum = 0
        self.trknum = 0
        self.bbox = (999, 999, -999, -999)
        try:
            file = open(filename)
            signature = file.read(2)
            file.close()
            file = {
                "BZ": lambda f: bz2.BZ2File(f),
                "\x1f\x8b": lambda f: gzip.GzipFile(f),
                "<?": lambda f: open(f),
            }[signature](filename)
        except (OSError, IOError):
            return
        try:
            doc = minidom.parse(file)
            doc.normalize()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            return  # handle this properly later
        gpx = doc.documentElement
        for node in gpx.getElementsByTagName("trk"):
            self.parseTrack(node)

    def parseTrack(self, trk):
        # name = trk.getElementsByTagName('name')[0].firstChild.data
        name = self.trknum
        self.trknum += 1
        if not name in self.tracks:
            self.tracks[name] = {}
        minlat, minlon, maxlat, maxlon = self.bbox
        for trkseg in trk.getElementsByTagName("trkseg"):
            for trkpt in trkseg.getElementsByTagName("trkpt"):
                lat = float(trkpt.getAttribute("lat"))
                lon = float(trkpt.getAttribute("lon"))
                if lat > maxlat:
                    maxlat = lat
                if lat < minlat:
                    minlat = lat
                if lon > maxlon:
                    maxlon = lon
                if lon < minlon:
                    minlon = lon
                #    ele = float(trkpt.getElementsByTagName('ele')[0].firstChild.data)
                rfc3339 = trkpt.getElementsByTagName("time")[0].firstChild.data
                self.pointnum += 1
                self.tracks[name][self.pointnum] = {"lat": lat, "lon": lon}
        self.bbox = (minlon, minlat, maxlon, maxlat)

    def getTrack(self, name):
        times = self.tracks[name].keys()
        times.sort()
        points = [self.tracks[name][time] for time in times]
        return [(point["lon"], point["lat"]) for point in points]
