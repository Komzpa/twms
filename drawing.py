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
import Image, ImageDraw
import urllib
import os, sys

import projections
import config
from gpxparse import GPXParser

def wkt(wkt, img, bbox, srs):
    """
    Simple WKT renderer
    """
    wkt = wkt.replace("((","(")
    for obj in wkt.split("),"):

       canvas = img.copy()
       name, coords = obj.split("(")
       coords = coords.replace(")","")
       coords = coords.split(",")
       coords = [ [float(t) for t in x.split(" ")] for x in coords]
       #coords = [(x[1],x[0]) for x in coords]
       canvas = render_vector(name, canvas, bbox, coords, srs)
       img = Image.blend(img, canvas, 0.5)
    return img

def gpx(track, img, bbox, srs):
    """
    Simple GPX renderer
    """



    for i in track.tracks.keys():
      coords = track.getTrack(i)
      #print >> sys.stderr, coords, "!!!!!!"
      #sys.stderr.flush()
      
      canvas = img.copy()
      canvas = render_vector("LINESTRING", canvas, bbox, coords, srs)
      img = Image.blend(img, canvas, 0.5)
    return img


def render_vector(geometry, img, bbox, coords, srs, color=None):
    """
    Renders a vector geometry on image.
    """
    if not color:
      color = config.geometry_color[geometry]
    draw = ImageDraw.Draw(img)
    bbox = projections.from4326(bbox, srs)
    lo1, la1, lo2, la2 = bbox
    
    coords = projections.from4326(coords, srs)
    W,H = img.size
    prevcoord = False
    coords = [(int((coord[0]-lo1)*(W-1)/abs(lo2-lo1)), int((la2-coord[1])*(H-1)/(la2-la1))) for coord in coords]

    if geometry == "LINESTRING":
       draw.line (coords, fill=color, width=3)


    elif geometry == "POINT":
       draw.ellipse((coords[0][0]-3,coords[0][1]-3,coords[0][0]+3,coords[0][1]+3),fill=color,outline=color)
    elif geometry == "POLYGON":
       draw.polygon(coords, fill=color, outline=color)
    return img