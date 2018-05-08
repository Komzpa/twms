# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

##
##  PP - PrePare
##  DL - DownLoading
##  RD - ReaDy
##



import projections

try:
    from PIL import Image, ImageFilter
except ImportError:
    import Image, ImageFilter

import urllib2
from io import BytesIO
import datetime
import sys
import threading

def debug(st):
  sys.stderr.write(str(st)+"\n")

class WmsCanvas:


   def __init__(self, wms_url = None, proj = "EPSG:4326", zoom = 4, tile_size = None, mode = "RGBA", tile_mode = "WMS"):
     self.wms_url = wms_url
     self.zoom = zoom
     self.proj = proj
     self.mode = mode
     self.tile_mode = tile_mode
     self.tile_height = 256
     self.tile_width = 256

     if tile_size:
       self.tile_width, self.tile_height = tile_size
     self.tiles = {}
   def __setitem__ (self, x, v):
     x, y = x
     tile_x = int(x/self.tile_height)
     x = x % self.tile_height
     tile_y = int(y/self.tile_width)
     y = y % self.tile_width
     try:
       self.tiles[(tile_x, tile_y)]["pix"][x,y] = v
     except KeyError:
       self.FetchTile(tile_x, tile_y)
       self.tiles[(tile_x, tile_y)]["pix"][x,y] = v
       
   def __getitem__ (self, x):
     x, y = x
     tile_x = int(x/self.tile_height)
     x = x % self.tile_height
     tile_y = int(y/self.tile_width)
     y = y % self.tile_width
     try:
       return self.tiles[(tile_x, tile_y)]["pix"][x,y]
     except KeyError:
       self.FetchTile(tile_x, tile_y)
       return self.tiles[(tile_x, tile_y)]["pix"][x,y]
       
   def ConstructTileUrl (self, x, y):
     if self.tile_mode == "WMS":
      a,b,c,d = projections.from4326(projections.bbox_by_tile(self.zoom, x, y, self.proj), self.proj)
      return self.wms_url + "width=%s&height=%s&srs=%s&bbox=%s,%s,%s,%s" % (self.tile_width, self.tile_height, self.proj, a,b,c,d)
     else:
      return self.wms_url + "z=%s&x=%s&y=%s&width=%s&height=%s" % (self.zoom-1, x, y, self.tile_width, self.tile_height)


   def FetchTile(self, x, y):
     if (x,y) in self.tiles:
       if self.tiles[(x, y)]["status"] == "DL":
         self.tiles[(x, y)]["thread"].join()
     else:
      im = ""
      if self.wms_url:
       remote = self.ConstructTileUrl (x, y)
       debug(remote)
       ttz = datetime.datetime.now()
       contents = urllib2.urlopen(remote).read()
       debug("Download took %s" % str(datetime.datetime.now() - ttz))
       im = Image.open(BytesIO(contents))
       if im.mode != self.mode:
         im = im.convert(self.mode)
      else:
       im = Image.new(self.mode, (self.tile_width,self.tile_height))
       debug("blanking tile")
      self.tiles[(x,y)] = {}
      self.tiles[(x,y)]["im"] = im
      self.tiles[(x,y)]["pix"] = im.load()
      self.tiles[(x, y)]["status"] = "RD"
      
   def PreparePixel(self, x, y):
     tile_x = int(x/self.tile_height)
     x = x % self.tile_height
     tile_y = int(y/self.tile_width)
     y = y % self.tile_width
     if not (tile_x, tile_y):
       self.tiles[(tile_x, tile_y)] = {}
       self.tiles[(tile_x, tile_y)]["status"] = "PP"     
     if not "pix" in self.tiles[(tile_x, tile_y)]:
       if self.tiles[(tile_x, tile_y)]["status"] == "PP":
         self.tiles[(tile_x, tile_y)]["status"] = "DL"
         self.tiles[(tile_x, tile_y)]["thread"] = threading.Thread(group=None, target=self.FetchTile, name=None, args=(self, tile_x, tile_y), kwargs={})
         self.tiles[(tile_x, tile_y)]["thread"].start()
     return self.tiles[(tile_x, tile_y)]["status"] == "RD"        


   def PixelAs4326(self,x,y):
      return projections.coords_by_tile(self.zoom, 1.*x/self.tile_width, 1.*y/self.tile_height, self.proj)
      
      
   def PixelFrom4326(self,lon,lat):
      a,b =  projections.tile_by_coords((lon, lat), self.zoom, self.proj)
      return a*self.tile_width, b*self.tile_height

   def MaxFilter(self, size = 5):
      tiles = self.tiles.keys()
      for tile in tiles:
        self.tiles[tile]["im"] = self.tiles[tile]["im"].filter(ImageFilter.MedianFilter(size))
        self.tiles[tile]["pix"] = self.tiles[tile]["im"].load()
