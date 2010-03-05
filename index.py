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

from PIL import Image, ImageDraw, ImageFilter, ImageOps
import os
import math
import sys
import urllib
try:
  import pyproj
except ImportError:
   pass
import ImageEnhance
import StringIO
import re
import time

import tilenames
import capabilities
import config
import bbox


if __name__ != '__main__':
 try: 
  from mod_python import apache, util
  import datetime  
 except ImportError:
   pass


layer = ""



 
def handler(req):
    """
    A handler for mod_python.
    """
    start_time = datetime.datetime.now()
    formats = {"image/gif":"GIF","image/jpeg":"JPEG","image/jpg":"JPEG","image/png":"PNG","image/bmp":"BMP"}

    data = util.FieldStorage(req)
    gpx = data.get("gpx",None) 
    if not gpx:
     req_bbox = "27.6518898,53.8683186,27.6581944,53.8720359"
    else:
     req_bbox = None
    width = 0
    height = 0
    zoom = 18
    layer = ""


   
    req_type = data.get("REQUEST",data.get("request","GetMap"))
    version = data.get("VERSION",data.get("version","1.1.1"))
    if req_type == "GetCapabilities":
     ctype, text = capabilities.get(version)
     req.content_type = ctype
     req.write (text)
     return apache.OK

    layer = data.get("layer",data.get("layers",data.get("LAYERS","osm")))
    format = data.get("format", data.get("FORMAT", config.default_format))
    if format not in formats:
     req.write("Invalid Format")
     return 500
    req.content_type = format
    x = int(data.get("x",data.get("X",0)))
    y = int(data.get("y",data.get("Y",0)))
    z = int(data.get("z",data.get("Z",1)))
    z += 1

    force = data.get("force","").split(",")
    filt = data.get ("filter","")
    if req_type == "GetTile":
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
      req_bbox = "%s,%s,%s,%s" % tilenames.tileEdges(x,y,z-1)







    if data.get("bbox",data.get("BBOX",None)) or req_bbox:
      req_bbox = tuple(map(float,data.get("bbox",data.get("BBOX",req_bbox)).split(",")))
    height = int(data.get("height",data.get("HEIGHT",height)))
    width = int(data.get("width",data.get("WIDTH",width)))
    srs = data.get("srs", data.get("SRS", "EPSG:4326"))
    if srs == "EPSG:4326":
       pass
       #p = pyproj.Proj("+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs")
    elif srs == "EPSG:3395":
        p = pyproj.Proj('+proj=merc +lon_0=0 +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs')
        la1,lo1,la2,lo2 = req_bbox
        la1,lo1 = p(la1,lo1, inverse=True)
        la2,lo2 = p(la2,lo2, inverse=True)
        req_bbox = (la1,lo1,la2,lo2)
    elif srs == "EPSG:900913" or srs == "EPSG:3857" :
        p = pyproj.Proj('+proj=merc +lon_0=0 +lat_ts=0 +x_0=0 +y_0=0 +a=6378137 +b=6378137 +units=m +no_defs')
        la1,lo1,la2,lo2 = req_bbox
        la1,lo1 = p(la1,lo1, inverse=True)
        la2,lo2 = p(la2,lo2, inverse=True)
        req_bbox = (la1,lo1,la2,lo2)

    req_bbox, flip_h, flip_v = bbox.normalize(req_bbox)

    if (width > 4048) or (height > 4048):
      width = 1024
      height = 0
    if (width == 0) and (height == 0):
      width = 350
    

    rovarinfo = data.get ("rovar", None)

    
    layer = layer.split(",")
    
    imgs = 1.
    result_img = getimg(req, req_bbox, (height, width), layer.pop(), gpx, rovarinfo, force, start_time)
    width, height =  result_img.size
    for ll in layer:
     result_img = Image.blend(result_img, getimg(req, req_bbox, (height, width), ll, gpx,  rovarinfo, force, start_time), imgs/(imgs+1.))
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
      wkt = wkt.replace("((","(")
      for obj in wkt.split("),"):

       wkt_canvas = result_img.copy()
       name, coords = obj.split("(")
       coords = coords.replace(")","")
       coords = coords.split(",")
       coords = [ [float(t) for t in x.split(" ")] for x in coords]
       coords = [(x[1],x[0]) for x in coords]
       render_vector(name,wkt_canvas, req_bbox,coords)
       result_img = Image.blend(result_img, wkt_canvas, 0.5)


    if flip_h:
      result_img = ImageOps.flip(result_img)
    if flip_v:
      result_img = ImageOps.mirror(result_img)
    
    result_img.save(req, formats[format])


    return apache.OK

def render_vector(geometry, img, bbox, coords):
    """
Renders a vector geomatry on image.
    """
    draw = ImageDraw.Draw(img)
    lo1, la1, lo2, la2 = bbox
    W,H = img.size
    prevcoord = False
    coords = [(int((coord[1]-lo1)*(W-1)/abs(lo2-lo1)), int((la2-coord[0])*(H-1)/(la2-la1))) for coord in coords]
    if geometry == "LINESTRING":
       draw.line (coords, fill="#ff0000", width=3)
       
       
    elif geometry == "POINT":
       draw.ellipse((coords[0][0]-3,coords[0][1]-3,coords[0][0]+3,coords[0][1]+3),fill="#00ee00",outline="#00ff00")
    elif geometry == "POLYGON":
       draw.polygon(coords, fill="#0000ff", outline="#0000cc")



def llz2txy(lat, lon, zoom=18, proj = 1):
    """
    Converts (lat,lon,zoom) to tile number and pixel-coordinates.
    proj is: 1 - default projection
             2 - Yandex projection
    """

    if proj == 1:    
            zoom = zoom-1
            sin_phi = math.sin(lat * math.pi /180);
            norm_x = lon / 180;
            norm_y = (0.5 * math.log((1 + sin_phi) / (1 - sin_phi))) / math.pi;
            this_y = math.pow(2, zoom) * ((1 - norm_y) / 2);
            this_x = math.pow(2, zoom) * ((norm_x + 1) / 2); 
            cut_x = int(256*(this_x - int(this_x)))
	    cut_y = int(256*(this_y - int(this_y)))
	    this_x = int(this_x)
	    this_y = int(this_y)
	    return (this_x, this_y, cut_x, cut_y)

    else:


        FINETUNE_X = 0#24
        FINETUNE_Y= 0#36

        M_PI_4 = 0.78539816339744830962
        YANDEX_Rn = 6378137.0
        YANDEX_E = 0.0818191908426
        YANDEX_A = 20037508.342789
        YANDEX_F = 53.5865938
        YANDEX_AB = 0.00335655146887969400
        YANDEX_BB = 0.00000657187271079536
        YANDEX_CB = 0.00000001764564338702
        YANDEX_DB = 0.00000000005328478445
        

        tmp=math.tan(M_PI_4+(lat*math.pi/180.)/2.0);
        pow_tmp = math.pow(math.tan(M_PI_4+math.asin(YANDEX_E*math.sin(lat*math.pi/180.))/2.0),YANDEX_E);
        x = (YANDEX_Rn*(lon*math.pi/180.) + YANDEX_A) * YANDEX_F;
        y = (YANDEX_A - (YANDEX_Rn * math.log (tmp / pow_tmp))) * YANDEX_F;

        this_x = (int(x/64)+FINETUNE_X)/256.0/(2**18)*(2**zoom)
	this_y = (int(y/64)+FINETUNE_Y)/256.0/(2**18)*(2**zoom)
        cut_x = int(256*(this_x - int(this_x)))
	cut_y = int(256*(this_y - int(this_y)))
	this_x = int(this_x)
	this_y = int(this_y)
	return (this_x, this_y, cut_x, cut_y)



def getbestzoom (bbox, size, layer):
   """
   Calculate a best-fit zoom level
   """
   max_zoom = config.layers[layer].get("max_zoom",18)
   for i in range (1,max_zoom):
     cx1, cy1, px1, py1 =  llz2txy (bbox[1],bbox[0], i, proj=config.layers[layer]["proj"])
     cx2, cy2, px2, py2 =  llz2txy (bbox[3],bbox[2], i, proj=config.layers[layer]["proj"])
     if size[1] is not 0:
      if ((cx2-cx1)*256+px2-px1) >= size[1] :
       return i
     if size[0] is not 0:
      if ((cy1-cy2)*256+py1-py2) >= size[0]:
       return i

   return max_zoom

def get_gpx_from_rovarinfo (id):
   import urllib2 
   
   route = urllib2.urlopen ("http://rovarinfo.rovarsoft.com/?q=route-display/%s"%id).read()
   rgexpr  = re.compile(r'LINESTRING\((.*)\)')
   line, = rgexpr.search(route).groups()
   coords = line.split(",")
   coords = [ [float(t) for t in x.split(" ")] for x in coords]
   coords = [(x[1],x[0]) for x in coords]
   return coords
   

   
   

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

def getimg (file, bbox, size, layer, gpx, rovarinfo, force, start_time):
   if gpx: 
     from gpxparse import GPXParser
     if not os.path.exists ("/var/www/latlon/wms/traces/%s.gpx" % gpx):
        urllib.urlretrieve ("http://www.openstreetmap.org/trace/%s/data" % gpx , "/var/www/latlon/wms/traces/%s.gpx" % gpx)
     track = GPXParser("/var/www/latlon/wms/traces/%s.gpx" % gpx)
     if not bbox:
      bbox = track.bbox          
   
   H,W = size
   
   zoom = getbestzoom (bbox,size,layer)
   lo1, la1, lo2, la2 = bbox
   from_tile_x, from_tile_y, cut_from_x, cut_from_y = llz2txy (la1,lo1,zoom,  proj=config.layers[layer]["proj"])
   to_tile_x, to_tile_y, cut_to_x, cut_to_y = llz2txy (la2,lo2,zoom, proj=config.layers[layer]["proj"])
   bbox = (cut_from_x, cut_to_y, 256*(to_tile_x-from_tile_x)+cut_to_x, 256*(from_tile_y-to_tile_y)+cut_from_y )
   x = 256*(to_tile_x-from_tile_x+1)
   y = 256*(from_tile_y-to_tile_y+1)

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
   
   
   if rovarinfo:
    draw = ImageDraw.Draw (out)
    prevcoord = None
    
    for coord in get_gpx_from_rovarinfo (rovarinfo):
       x = int((coord[1]-lo1)*(W-1)/abs(lo2-lo1))
       y = int((la2-coord[0])*(H-1)/(la2-la1))
       if not prevcoord:
          prevcoord = (x,y)	
       draw.line ([prevcoord, (x,y)], fill="#FF7F24", width=3)
       draw.line ([ (x,y), prevcoord], fill="#FF7F24", width=3)
       if math.sqrt(reduce(lambda a,b: a*a+b*b,map(lambda c,d: abs(c-d) ,(x,y),prevcoord))) > 4:
        prevcoord = (x,y)       
   if gpx:
    draw = ImageDraw.Draw (out)

    
    for i in track.tracks.keys(): 
     prevcoord = None     
     for coord in track.getTrack(i):
     #for coord in get_gpx_from_rovarinfo (3):
       x = int((coord[1]-lo1)*(W-1)/abs(lo2-lo1))
       y = int((la2-coord[0])*(H-1)/(la2-la1))
       if not prevcoord:
          prevcoord = (x,y)	
       draw.line ([prevcoord, (x,y)], fill="#FF7F24", width=3)
       draw.line ([ (x,y), prevcoord], fill="#FF7F24", width=3)
       #draw.line ([prevcoord, (x,y)], fill="#FF0000", width=1)
       draw.line ([ (x,y), (x,y)], fill="#FF0000", width=1)

       if math.sqrt(reduce(lambda a,b: a*a+b*b,map(lambda c,d: abs(c-d) ,(x,y),prevcoord))) > 4:
        prevcoord = (x,y)
   return out