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

import sys, string
from xml.dom import minidom, Node

class GPXParser:
  def __init__(self, filename):
    self.tracks = {}
    self.pointnum = 0
    self.trknum = 0
    self.bbox = (999,999,-999,-999)
    try:
      doc = minidom.parse(filename)
      doc.normalize()
    except:
      return # handle this properly later
    gpx = doc.documentElement
    for node in gpx.getElementsByTagName('trk'):
      self.parseTrack(node)

  def parseTrack(self, trk):
    #name = trk.getElementsByTagName('name')[0].firstChild.data
    name = self.trknum
    self.trknum += 1
    if not name in self.tracks:
      self.tracks[name] = {}
    minlat, minlon, maxlat, maxlon = self.bbox
    for trkseg in trk.getElementsByTagName('trkseg'):
      for trkpt in trkseg.getElementsByTagName('trkpt'):
        
        lat = float(trkpt.getAttribute('lat'))
        lon = float(trkpt.getAttribute('lon'))
	if lat > maxlat:
          maxlat = lat
        if lat < minlat:
          minlat = lat
        if lon > maxlon:
          maxlon = lon
        if lon < minlon:
          minlon = lon
    #    ele = float(trkpt.getElementsByTagName('ele')[0].firstChild.data)
        rfc3339 = trkpt.getElementsByTagName('time')[0].firstChild.data
	self.pointnum += 1
        self.tracks[name][self.pointnum]={'lat':lat,'lon':lon}
    self.bbox = (minlon, minlat, maxlon, maxlat)

  def getTrack(self, name):
    times = self.tracks[name].keys()
    times.sort()
    points = [self.tracks[name][time] for time in times]
    return [(point['lat'],point['lon']) for point in points]
