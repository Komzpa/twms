# -*- coding: utf-8 -*-
import urllib
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
   ic = Image.new("RGBA", (256, 256), "white")
   if im.histogram() == ic.histogram():
      tne = open (local+"tne", "w")
      when = time.localtime()
      tne.write("%02d.%02d.%04d %02d:%02d:%02d"%(when[2],when[1],when[0],when[3],when[4],when[5]))
      tne.close()
      os.remove(local+ this_layer["ext"])
      return False
   im.save(local+this_layer["ext"])
   os.rmdir(local+"lock")
   return local+this_layer["ext"]
   
def Tile (z, x, y, layer):

   n1,n2,n3 = z,x,y
   this_layer = config.layers[layer]
   if "max_zoom" in this_layer:
    if z >= this_layer["max_zoom"]:
      return None
   if "transform_tile_number" in this_layer:
    n1,n2,n3 = this_layer["transform_tile_number"](z,x,y)
   remote = this_layer["remote_url"]%(n1,n2,n3)
   local = config.tiles_cache + this_layer["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
   if not os.path.exists("/".join(local.split("/")[:-1])):
       os.makedirs("/".join(local.split("/")[:-1]))
   try:
    os.mkdir(local+"lock")
   except OSError:
    return None
   urllib.urlretrieve (remote, local+ this_layer["ext"])
   os.rmdir(local+"lock")
   if not os.path.exists(local+ this_layer["ext"]):
      return False
   if "dead_tile" in this_layer:
    if filecmp.cmp(local+this_layer["ext"], this_layer["dead_tile"]):
      tne = open (local+"tne", "w")
      when = time.localtime()
      tne.write("%02d.%02d.%04d %02d:%02d:%02d"%(when[2],when[1],when[0],when[3],when[4],when[5]))
      tne.close()
      os.remove(local+ this_layer["ext"])
      return False
   return local+this_layer["ext"]