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

from PIL import Image, ImageFilter, ImageOps
import os
import math
import sys
import urllib
import ImageEnhance
import StringIO
import re
import time

import capabilities
import config
import bbox
import projections
import drawing
from gpxparse import GPXParser

if __name__ != '__main__':
 try: 
  from mod_python import apache, util
  import datetime  
 except ImportError:
   pass

 
def handler(req):
    """
    A handler for mod_python.
    """
    start_time = datetime.datetime.now()
    formats = {"image/gif":"GIF","image/jpeg":"JPEG","image/jpg":"JPEG","image/png":"PNG","image/bmp":"BMP"}

    data = util.FieldStorage(req)
    srs = data.get("srs", data.get("SRS", "EPSG:4326"))
    gpx = data.get("gpx",None)
    track = False
    if not gpx:
      req_bbox = projections.from4326((27.6518898,53.8683186,27.6581944,53.8720359), srs)
    else:
      local_gpx = config.gpx_cache + "%s.gpx" % gpx
      if not os.path.exists (local_gpx):
          urllib.urlretrieve ("http://www.openstreetmap.org/trace/%s/data" % gpx, local_gpx)
      track = GPXParser(local_gpx)
      req_bbox = projections.from4326(track.bbox, srs)
    width = 0
    height = 0

    

   
    req_type = data.get("REQUEST",data.get("request","GetMap"))
    version = data.get("VERSION",data.get("version","1.1.1"))
    if req_type == "GetCapabilities":
     ctype, text = capabilities.get(version)
     req.content_type = ctype
     req.write (text)
     return apache.OK

    layer = data.get("layers",data.get("LAYERS", config.default_layers))
    format = data.get("format", data.get("FORMAT", config.default_format))
    if format not in formats:
     req.write("Invalid Format")
     return 500
    req.content_type = format


    force = data.get("force","").split(",")
    filt = data.get ("filter","")
    if req_type == "GetTile":
      srs = data.get("srs", data.get("SRS", "EPSG:3857"))
      x = int(data.get("x",data.get("X",0)))
      y = int(data.get("y",data.get("Y",0)))
      z = int(data.get("z",data.get("Z",1))) + 1
      width=256
      height=256
      height = int(data.get("height",data.get("HEIGHT",height)))
      width = int(data.get("width",data.get("WIDTH",width)))
      if data.get("layer",data.get("layers",data.get("LAYERS","osm"))) in config.layers:
       if config.layers[layer]["proj"] is 1 and width is 256 and height is 256 and not filt and not force:
          local = config.tiles_cache + config.layers[layer]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
          ext = config.layers[layer]["ext"]
          adds = ["","ups."]
          for add in adds:
           if os.path.exists(local+add+ext):
             tile_file = open(local+add+ext, "r")
             req.write(tile_file.read())
             return apache.OK
      req_bbox = projections.from4326(projections.bbox_by_tile(z,x,y,srs),srs)


    if data.get("bbox",data.get("BBOX",None)):
      req_bbox = tuple(map(float,data.get("bbox",data.get("BBOX",req_bbox)).split(",")))

    height = int(data.get("height",data.get("HEIGHT",height)))
    width = int(data.get("width",data.get("WIDTH",width)))
    req_bbox = projections.to4326(req_bbox, srs)   

    req_bbox, flip_h, flip_v = bbox.normalize(req_bbox)
    print >> sys.stderr, req_bbox
    sys.stderr.flush()

    if (width > 4048) or (height > 4048):
      width = 1024
      height = 0
    if (width == 0) and (height == 0):
      width = 350
    

    layer = layer.split(",")
    
    imgs = 1.
    result_img = getimg(req, req_bbox, (height, width), layer.pop(), force, start_time)
    width, height =  result_img.size
    for ll in layer:
     result_img = Image.blend(result_img, getimg(req, req_bbox, (height, width), ll, force, start_time), imgs/(imgs+1.))
     imgs += 1.

##Applying filters
    for ff in filt.split(","):
     if ff.split(":") == [ff,]:
      if ff == "bw":
       r,g,b = result_img.split()
       g = g.filter(ImageFilter.CONTOUR)
       result_img = Image.merge ("RGB", (r,g,b))

       result_img = Image.eval(result_img, lambda x: int((x+512)/3))
       outtbw = result_img.convert("L")

       outtbw = outtbw.convert("RGB")
       result_img = Image.blend(result_img, outtbw, 0.62)
      if ff == "contour":
        result_img = result_img.filter(ImageFilter.CONTOUR)
      if ff == "median":
        result_img = result_img.filter(ImageFilter.MedianFilter(5))
      if ff == "blur":
        result_img = result_img.filter(ImageFilter.BLUR)
      if ff == "edge":
        result_img = result_img.filter(ImageFilter.EDGE_ENHANCE)
     else:
      ff, tt = ff.split(":")
      tt = float(tt)
      if ff == "brightness":
        enhancer = ImageEnhance.Brightness(result_img)
        result_img = enhancer.enhance(tt)
      if ff == "contrast":
        enhancer = ImageEnhance.Contrast(result_img)
        result_img = enhancer.enhance(tt)
      if ff == "sharpness":
        enhancer = ImageEnhance.Sharpness(result_img)
        result_img = enhancer.enhance(tt)



    wkt = data.get("wkt",data.get("WKT",None))
    
    if wkt: 
      result_img = drawing.wkt(wkt, result_img, req_bbox, srs)
    if gpx:
      result_img = drawing.gpx(track, result_img, req_bbox, srs)

    if flip_h:
      result_img = ImageOps.flip(result_img)
    if flip_v:
      result_img = ImageOps.mirror(result_img)
    
    result_img.save(req, formats[format])


    return apache.OK



def getbestzoom (bbox, size, layer):
   """
   Calculate a best-fit zoom level
   """
   max_zoom = config.layers[layer].get("max_zoom",config.default_max_zoom)
   for i in range (1,max_zoom):
     cx1, cy1, cx2, cy2 =  projections.tile_by_bbox (bbox, i, config.layers[layer]["proj"])
     if size[1] is not 0:
      if (cx2-cx1)*256 >= size[1] :
       return i
     if size[0] is not 0:
      if (cy1-cy2)*256 >= size[0]:
       return i

   return max_zoom

def tile_image (layer, z, x, y, start_time, again=False, trybetter = True, real = False):
   """
   Returns asked image.
   again - is this a second pass on this tile?
   trybetter - should we try to combine this tile from better ones?
   real - should we return the tile even in not good quality?
   """
   x = x % (2 ** (z-1))
   if y<0 or y >= (2 ** (z-1)):
     return None
   if config.layers[layer].get("cached", True):
    local = config.tiles_cache + config.layers[layer]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
    ext = config.layers[layer]["ext"]
    if "cache_ttl" in config.layers[layer]:
      for ex in [ext, "dsc."+ext, "ups."+ext, "tne"]:
       f = local+ex
       if os.path.exists(f):
         if (os.stat(f).st_mtime < (time.time()-config.layers[layer]["cache_ttl"])):
           os.remove(f)

    gpt_image = False
    if not os.path.exists("/".join(local.split("/")[:-1])):
        os.makedirs("/".join(local.split("/")[:-1]))
    if not os.path.exists(local+"tne") and not os.path.exists(local+"lock"):
      if os.path.exists(local+ext):			# First, look for tile in cache
        try:
            im1 = Image.open(local+ext)
            a = im1.load()
            return im1
        except IOError:
          if os.path.exists(local+"lock"):
            return None
          else:
            os.remove(local+ext)				# # Cached tile is broken - remove it


      if config.layers[layer]["scalable"] and (z<18) and trybetter:      # Second, try to glue image of better ones
          if os.path.exists(local+"ups."+ext):
              im = Image.open(local+"ups."+ext)
              return im
          im = Image.new("RGBA", (512, 512), (0,0,0,0))
          im1 = tile_image(layer, z+1,x*2,y*2, start_time)
          if im1:
           im2 = tile_image(layer, z+1,x*2+1,y*2, start_time)
           if im2:
            im3 = tile_image(layer, z+1,x*2,y*2+1, start_time)
            if im3:
              im4 = tile_image(layer, z+1,x*2+1,y*2+1, start_time)
              if im4:
                im.paste(im1,(0,0))
                im.paste(im2,(256,0))
                im.paste(im3,(0,256))
                im.paste(im4,(256,256))
                im = im.resize((256,256),Image.ANTIALIAS)
                im.save(local+"ups."+ext)
                return im
      if not again:

        if "fetch" in config.layers[layer]:
          delta = (datetime.datetime.now() - start_time)
          delta = delta.seconds + delta.microseconds/1000000.
          if (config.deadline > delta) or (z < 4):

            im = config.layers[layer]["fetch"](z,x,y,layer)    # Try fetching from outside
            if im:
              return im
    if real and (z>1):
          im = tile_image(layer, z-1, int(x/2), int(y/2), start_time,  again=False, trybetter=False, real=True)
          if im:
            im = im.crop((128 * (x % 2), 128 * (y % 2), 128 * (x % 2) + 128, 128 * (y % 2) + 128))
            im = im.resize((256,256), Image.BILINEAR)
            return im
   else:
      if "fetch" in config.layers[layer]:
          delta = (datetime.datetime.now() - start_time)
          delta = delta.seconds + delta.microseconds/1000000.
          if (config.deadline > delta) or (z < 4):

            im = config.layers[layer]["fetch"](z,x,y,layer)    # Try fetching from outside
            if im:
              return im

def getimg (file, bbox, size, layer, force, start_time):
   
   H,W = size
   
   zoom = getbestzoom (bbox,size,layer)
   lo1, la1, lo2, la2 = bbox
   from_tile_x, from_tile_y, to_tile_x, to_tile_y = projections.tile_by_bbox(bbox, zoom, config.layers[layer]["proj"])
   cut_from_x = int(256*(from_tile_x - int(from_tile_x)))
   cut_from_y = int(256*(from_tile_y - int(from_tile_y)))
   cut_to_x = int(256*(to_tile_x - int(to_tile_x)))
   cut_to_y = int(256*(to_tile_y - int(to_tile_y)))
    
   from_tile_x, from_tile_y = int(from_tile_x), int(from_tile_y)
   to_tile_x, to_tile_y = int(to_tile_x), int(to_tile_y)
   bbox = (cut_from_x, cut_to_y, 256*(to_tile_x-from_tile_x)+cut_to_x, 256*(from_tile_y-to_tile_y)+cut_from_y )
   x = 256*(to_tile_x-from_tile_x+1)
   y = 256*(from_tile_y-to_tile_y+1)
   print >> sys.stderr, x, y
   sys.stderr.flush()
   out = Image.new("RGBA", (x, y))
   for x in range (from_tile_x, to_tile_x+1):
    for y in range (to_tile_y, from_tile_y+1):
     got_image = False
     im1 = tile_image (layer,zoom,x,y, start_time, real = True)
     if not im1:
        im1 = Image.new("RGBA", (256, 256), (0,0,0,0))


     out.paste(im1,((x - from_tile_x)*256, (-to_tile_y + y )*256,))
   out = out.crop(bbox)
   if (H == W) and (H == 0):
     W, H = out.size
   if H == 0:
     H = out.size[1]*W/out.size[0]
   if W == 0:
     W = out.size[0]*H/out.size[1]
   
   if "noresize" not in force:
    out = out.resize((W,H), Image.ANTIALIAS)

   return out