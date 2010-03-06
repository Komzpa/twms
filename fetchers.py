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

import urllib2
import filecmp
import time
import os
import math
import sys
import StringIO
import Image
import tilenames
import config


def Wms4326as3857 (z, x, y, layer):

   this_layer = config.layers[layer]
   if "max_zoom" in this_layer:
    if z >= this_layer["max_zoom"]:
      return None   
   wms = this_layer["wms_4326"]
   width = 384   # using larger source size to rescale better in python
   height = 384
   local = config.tiles_cache + this_layer["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
   tile_bbox = "bbox=%s,%s,%s,%s" % tilenames.tileEdges(x,y,z-1)

   wms += tile_bbox + "&width=%s&height=%s"%(width, height)
   if this_layer.get("cached", True):
    if not os.path.exists("/".join(local.split("/")[:-1])):
        os.makedirs("/".join(local.split("/")[:-1]))
    try:
       os.mkdir(local+"lock")
    except OSError:
        return None
   im = Image.open(StringIO.StringIO(urllib2.urlopen(wms).read()))
   if width is not 256 and height is not 256:
    im = im.resize((256,256),Image.ANTIALIAS)
   im = im.convert("RGBA")
   
   if this_layer.get("cached", True):
    ic = Image.new("RGBA", (256, 256), "white")
    if im.histogram() == ic.histogram():
       tne = open (local+"tne", "wb")
       when = time.localtime()
       tne.write("%02d.%02d.%04d %02d:%02d:%02d"%(when[2],when[1],when[0],when[3],when[4],when[5]))
       tne.close()
       return False
   
    im.save(local+this_layer["ext"])
    os.rmdir(local+"lock")
   return im
   
def Tile (z, x, y, layer):

   d_tuple = z,x,y
   this_layer = config.layers[layer]
   if "max_zoom" in this_layer:
    if z >= this_layer["max_zoom"]:
      return None
   if "transform_tile_number" in this_layer:
    d_tuple = this_layer["transform_tile_number"](z,x,y)
   print >> sys.stderr, x, y, z
   sys.stderr.flush()
   remote = this_layer["remote_url"] % d_tuple
   if this_layer.get("cached", True):
    local = config.tiles_cache + this_layer["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
    if not os.path.exists("/".join(local.split("/")[:-1])):
       os.makedirs("/".join(local.split("/")[:-1]))
    try:
        os.mkdir(local+"lock")
    except OSError:
      return None
   
   try:
     contents = urllib2.urlopen(remote).read()
     im = Image.open(StringIO.StringIO(contents))  
   except IOError:
     if this_layer.get("cached", True):
       os.rmdir(local+"lock")
     return False
   if this_layer.get("cached", True):
     os.rmdir(local+"lock")
     open(local+ this_layer["ext"], "wb").write(contents)
   
   if "dead_tile" in this_layer:
    dt = open(this_layer["dead_tile"],"r").read()
    if contents == dt:
      if this_layer.get("cached", True):
        tne = open (local+"tne", "wb")
        when = time.localtime()
        tne.write("%02d.%02d.%04d %02d:%02d:%02d"%(when[2],when[1],when[0],when[3],when[4],when[5]))
        tne.close()
        os.remove(local+ this_layer["ext"])
      return False
   return im