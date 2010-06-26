#!/usr/bin/python
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

from PIL import Image, ImageOps, ImageColor
import os
import math
import sys
import urllib
import StringIO
import time
import datetime


import correctify
import capabilities
import config
import bbox
import projections
import drawing
import filter
import overview
from gpxparse import GPXParser
from reproject import reproject

try:
        import psyco
        psyco.full()
except ImportError:
        pass


       


OK = 200
ERROR = 500

cached_objs = {}        # a dict. (layer, z, x, y): PIL image
cached_hist_list = []


print >> sys.stderr, "New copy started"
sys.stderr.flush()



def twms_main(req):
    """
    Do main TWMS work. 
    req - dictionary of params. 
    returns (error_code, content_type, data)
    """

    #print >> sys.stderr, len(cached_objs), " --- cached items"
    #sys.stderr.flush()
    
    
    
    start_time = datetime.datetime.now()
    formats = {"image/gif":"GIF","image/jpeg":"JPEG","image/jpg":"JPEG","image/png":"PNG","image/bmp":"BMP"}
    content_type = "text/html"
    resp = ""
    data = req
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

    req_type = data.get("REQUEST",data.get("request","GetMap"))
    version = data.get("VERSION",data.get("version","1.1.1"))
    ref = data.get("ref",config.service_url)
    if req_type == "GetCapabilities":
     content_type, resp = capabilities.get(version, ref)
     return (OK, content_type, resp)

    layer = data.get("layers",data.get("LAYERS", config.default_layers)).split(",")
    if req_type == "GetCorrections":
       points = data.get("points",data.get("POINTS", "")).split("=")
       resp = ""
       points = [a.split(",") for a in points]
       points = [(float(a[0]), float(a[1])) for a in points]

       req.content_type = "text/plain"
       for lay in layer:
         for point in points:
           resp += "%s,%s;"% tuple(correctify.rectify(config.layers[lay], point))
         resp += "\n"
       return (OK, content_type, resp)


    force = data.get("force","").split(",")
    filt = data.get ("filter","").split(",")
    if layer == [""] :
      content_type = "text/html"
      resp = overview.html(ref)
      return (OK, content_type, resp)

    format = data.get("format", data.get("FORMAT", config.default_format))
    if format not in formats:
       return (ERROR, content_type, "Invalid format")
    content_type = format

    width=0
    height=0
    if req_type == "GetTile":
      width=256
      height=256
      height = int(data.get("height",data.get("HEIGHT",height)))
      width = int(data.get("width",data.get("WIDTH",width)))
      srs = data.get("srs", data.get("SRS", "EPSG:3857"))
      x = int(data.get("x",data.get("X",0)))
      y = int(data.get("y",data.get("Y",0)))
      z = int(data.get("z",data.get("Z",1))) + 1
      if len(layer) == 1:
       if layer[0] in config.layers:
        if config.layers[layer[0]]["proj"] == srs and width is 256 and height is 256 and not filt and not force:
          local = config.tiles_cache + config.layers[layer[0]]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
          ext = config.layers[layer]["ext"]
          adds = ["","ups."]
          for add in adds:
           if os.path.exists(local+add+ext):
             tile_file = open(local+add+ext, "r")
             resp = tile_file.read()
             return (OK, content_type, resp)
      req_bbox = projections.from4326(projections.bbox_by_tile(z,x,y,srs),srs)

    if data.get("bbox",data.get("BBOX",None)):
      req_bbox = tuple(map(float,data.get("bbox",data.get("BBOX",req_bbox)).split(",")))

    req_bbox = projections.to4326(req_bbox, srs)

    req_bbox, flip_h = bbox.normalize(req_bbox)
    box = req_bbox
    #print >> sys.stderr, req_bbox
    #sys.stderr.flush()

    height = int(data.get("height",data.get("HEIGHT",height)))
    width = int(data.get("width",data.get("WIDTH",width)))
    width = min(width, config.max_width)
    height = min(height, config.max_height)
    if (width == 0) and (height == 0):
      width = 350


   # layer = layer.split(",")

    imgs = 1.
    ll = layer.pop(0)
    if "nocorrect" not in force:
      box = correctify.r_bbox(config.layers[ll], req_bbox)

    result_img = getimg(box, (height, width), config.layers[ll], start_time)

    if "noresize" not in force:
      if (height == width) and (height == 0):
        width, height = result_img.size
      if height == 0:
        height = result_img.size[1]*width/result_img.size[0]
      if width == 0:
        width = result_img.size[0]*height/result_img.size[1]
      result_img = result_img.resize((width,height), Image.ANTIALIAS)
    #width, height =  result_img.size
    for ll in layer:
     if "nocorrect" not in force:
        box = correctify.r_bbox(config.layers[ll], req_bbox)
     im2 = getimg(box, (height, width), config.layers[ll],  start_time)

     if "empty_color" in config.layers[ll]:
      ec = ImageColor.getcolor(config.layers[ll]["empty_color"], "RGBA")

      i2l = im2.load()
      for x in range(0,im2.size[0]):
        for y in range(0,im2.size[1]):
          t = i2l[x,y]
          #print >> sys.stderr, ec, t, ec == t
          #sys.stderr.flush()

          if ec == t:
            i2l[x,y] = (t[0],t[1],t[2],0)
     if not im2.size == result_img.size:
         im2 = im2.resize(result_img.size, Image.ANTIALIAS)
     im2 = Image.composite(im2,result_img, im2.split()[3]) # imgs/(imgs+1.))

     if "noblend" in force:
      result_img = im2
     else:
      result_img = Image.blend(im2, result_img, 0.5)
     imgs += 1.

    ##Applying filters
    result_img = filter.raster(result_img, filt)
    wkt = data.get("wkt",data.get("WKT",None))

    if wkt:
      result_img = drawing.wkt(wkt, result_img, req_bbox, srs)
    if gpx:
      result_img = drawing.gpx(track, result_img, req_bbox, srs)

    if flip_h:
      result_img = ImageOps.flip(result_img)
    image_content = StringIO.StringIO()

    if formats[format] == "JPEG":
       try:
        result_img.save(image_content, formats[format], quality=config.output_quality, progressive=config.output_progressive)
       except IOError:
        result_img.save(image_content, formats[format], quality=config.output_quality)
    elif formats[format] == "PNG":
       result_img.save(image_content, formats[format], progressive=config.output_progressive, optimize =config.output_optimize)
    elif formats[format] == "GIF":
       result_img.save(image_content, formats[format], quality=config.output_quality, progressive=config.output_progressive)
    else:       ## workaround for GIF
       result_img = result_img.convert("RGB")
       result_img.save(image_content, formats[format], quality=config.output_quality, progressive=config.output_progressive)
    resp = image_content.getvalue()
    return (OK, content_type, resp)



def getbestzoom (bbox, size, layer):
   """
   Calculate a best-fit zoom level
   """
   max_zoom = layer.get("max_zoom",config.default_max_zoom)
   min_zoom = layer.get("min_zoom",1)
   h,w = size
   for i in range (min_zoom,max_zoom):
     cx1, cy1, cx2, cy2 =  projections.tile_by_bbox (bbox, i, layer["proj"])
     if w is not 0:
      if (cx2-cx1)*256 >= w :
       return i
     if h is not 0:
      if (cy1-cy2)*256 >= h:
       return i
     if (cy1-cy2)*256 >= config.max_height/2:
       return i
     if (cx2-cx1)*256 >= config.max_width/2:
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
   if not bbox.bbox_is_in(projections.bbox_by_tile(z,x,y,layer["proj"]), layer.get("data_bounding_box",config.default_bbox), fully=False):
     return None
     
   global cached_objs, cached_hist_list
   if "prefix" in layer:
     if (layer["prefix"], z, x, y) in cached_objs:
      return cached_objs[(layer["prefix"], z, x, y)]
   if layer.get("cached", True):
    local = config.tiles_cache + layer["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
    ext = layer["ext"]
    if "cache_ttl" in layer:
      for ex in [ext, "dsc."+ext, "ups."+ext, "tne"]:
       f = local+ex
       if os.path.exists(f):
         if (os.stat(f).st_mtime < (time.time()-layer["cache_ttl"])):
           os.remove(f)

    gpt_image = False
    try:
      "trying to create local cache directory, if it doesn't exist"
      os.makedirs("/".join(local.split("/")[:-1]))
    except OSError:
      pass
    if not os.path.exists(local+"tne") and not os.path.exists(local+"lock"):
      if os.path.exists(local+ext):                     # First, look for tile in cache
        try:
            im1 = Image.open(local+ext)
            a = im1.load()
            return im1
        except IOError:
          if os.path.exists(local+"lock"):
            return None
          else:
            os.remove(local+ext)                                # # Cached tile is broken - remove it


      if layer["scalable"] and (z<layer.get("max_zoom", config.default_max_zoom)) and trybetter:      # Second, try to glue image of better ones
          if os.path.exists(local+"ups."+ext):
              im = Image.open(local+"ups."+ext)
              return im
          ec = ImageColor.getcolor(layer.get("empty_color", config.default_background), "RGBA")
          ec = (ec[0],ec[1],ec[2],0)
          im = Image.new("RGBA", (512, 512), ec)
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
                if layer.get("cached", True):
                  im.save(local+"ups."+ext)
                return im
      if not again:

        if "fetch" in layer:
          delta = (datetime.datetime.now() - start_time)
          delta = delta.seconds + delta.microseconds/1000000.
          if (config.deadline > delta) or (z < 4):

            im = layer["fetch"](z,x,y,layer)    # Try fetching from outside
            if im:
              return im
    if real and (z>1):
          im = tile_image(layer, z-1, int(x/2), int(y/2), start_time,  again=False, trybetter=False, real=True)
          if im:
            im = im.crop((128 * (x % 2), 128 * (y % 2), 128 * (x % 2) + 128, 128 * (y % 2) + 128))
            im = im.resize((256,256), Image.BILINEAR)
            return im
   else:
      if "fetch" in layer:
          delta = (datetime.datetime.now() - start_time)
          delta = delta.seconds + delta.microseconds/1000000.
          if (config.deadline > delta) or (z < 4):

            im = layer["fetch"](z,x,y,layer)    # Try fetching from outside
            if im:
              return im

def getimg (bbox, size, layer, start_time):
  
   global cached_objs
   H,W = size

   zoom = getbestzoom (bbox,size,layer)
   lo1, la1, lo2, la2 = bbox
   from_tile_x, from_tile_y, to_tile_x, to_tile_y = projections.tile_by_bbox(bbox, zoom, layer["proj"])
   cut_from_x = int(256*(from_tile_x - int(from_tile_x)))
   cut_from_y = int(256*(from_tile_y - int(from_tile_y)))
   cut_to_x = int(256*(to_tile_x - int(to_tile_x)))
   cut_to_y = int(256*(to_tile_y - int(to_tile_y)))

   from_tile_x, from_tile_y = int(from_tile_x), int(from_tile_y)
   to_tile_x, to_tile_y = int(to_tile_x), int(to_tile_y)
   bbox_im = (cut_from_x, cut_to_y, 256*(to_tile_x-from_tile_x)+cut_to_x, 256*(from_tile_y-to_tile_y)+cut_from_y )
   x = 256*(to_tile_x-from_tile_x+1)
   y = 256*(from_tile_y-to_tile_y+1)
   #print >> sys.stderr, x, y
   #sys.stderr.flush()
   out = Image.new("RGBA", (x, y))
   for x in range (from_tile_x, to_tile_x+1):
    for y in range (to_tile_y, from_tile_y+1):
     got_image = False
     im1 = tile_image (layer,zoom,x,y, start_time, real = True)
     if im1:
      if "prefix" in layer:
       if (layer["prefix"], zoom, x, y) not in cached_objs:
          cached_objs[(layer["prefix"], zoom, x, y)] = im1
          cached_hist_list.append((layer["prefix"], zoom, x, y))
          #print >> sys.stderr, (layer["prefix"], zoom, x, y), cached_objs[(layer["prefix"], zoom, x, y)]
          #sys.stderr.flush()
       if len(cached_objs) >= config.max_ram_cached_tiles:
          del cached_objs[cached_hist_list.pop(0)]
          #print >> sys.stderr, "Removed tile from cache", 
          #sys.stderr.flush()
     else:
          ec = ImageColor.getcolor(layer.get("empty_color", config.default_background), "RGBA")
          #ec = (ec[0],ec[1],ec[2],0)
          im1 = Image.new("RGBA", (256, 256), ec)


     out.paste(im1,((x - from_tile_x)*256, (-to_tile_y + y )*256,))
   out = out.crop(bbox_im)
   #out = reproject(out, bbox, layer["proj"], "EPSG:4326")
   return out
