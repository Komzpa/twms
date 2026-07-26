# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

import bz2
import gzip
from xml.dom import minidom


class GPXParser:
    def __init__(self, filename):
        self.tracks = {}
        self.pointnum = 0
        self.trknum = 0
        self.bbox = (999, 999, -999, -999)
        try:
            with open(filename, "rb") as probe:
                signature = probe.read(2)
            gpx_file = {
                b"BZ": lambda f: bz2.BZ2File(f),
                b"\x1f\x8b": lambda f: gzip.GzipFile(f),
                b"<?": lambda f: open(f, "rb"),
            }[signature](filename)
        except (OSError, IOError, KeyError):
            return
        try:
            doc = minidom.parse(gpx_file)
            doc.normalize()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            return  # handle this properly later
        finally:
            gpx_file.close()
        gpx = doc.documentElement
        for node in gpx.getElementsByTagName("trk"):
            self.parseTrack(node)

    def parseTrack(self, trk):
        # name = trk.getElementsByTagName('name')[0].firstChild.data
        name = self.trknum
        self.trknum += 1
        if name not in self.tracks:
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
                self.pointnum += 1
                self.tracks[name][self.pointnum] = {"lat": lat, "lon": lon}
        self.bbox = (minlon, minlat, maxlon, maxlat)

    def getTrack(self, name):
        """Return track points in the original parsed order."""

        times = sorted(self.tracks[name].keys())
        points = [self.tracks[name][time] for time in times]
        return [(point["lon"], point["lat"]) for point in points]
