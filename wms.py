# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw
import os
import math

if __name__ != '__main__':
 
 from mod_python import apache, util
 import datetime  


bbox = (27.6518898,53.8683186,27.6581944,53.8720359)
width = 499
height = 500
zoom = 18
layer = "gshtab"

 
def handler(req):
    req.content_type = "image/jpeg"
    data = util.FieldStorage(req)
    bbox = tuple(map(float,data.get("bbox", "27.6542476,53.8656328,27.6623148,53.8703895").split(",")))
    height = int(data.get("height",500))
    width = int(data.get("width",499))
    layer = data.get("layer","gshtab")
    getimg(req,bbox, (height, width), layer)
    
    return apache.OK




def llz2txy(lat, lon, zoom=18):
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





def getimg (file, bbox, size, layer):
   W,H = size
   

   lo1, la1, lo2, la2 = bbox
   from_tile_x, from_tile_y, cut_from_x, cut_from_y = llz2txy (la1,lo1)
   to_tile_x, to_tile_y, cut_to_x, cut_to_y = llz2txy (la2,lo2)
   bbox = (cut_from_x, cut_to_y, 256*(to_tile_x-from_tile_x)+cut_to_x, 256*(from_tile_y-to_tile_y)+cut_from_y )
   x = 256*(to_tile_x-from_tile_x+1)
   y = 256*(from_tile_y-to_tile_y+1)
   out = Image.new("RGB", (x, y), None)
   for x in range (from_tile_x, to_tile_x+1):
    for y in range (to_tile_y, from_tile_y+1):
     fname = "/var/www/latlon/wms/cache/%s/z%s/%s/x%s/%s/y%s.jpg"%(layer, zoom, x/1024, x, y/1024, y )
     print fname
     if os.path.exists(fname):
          im1 = Image.open(fname)
	  out.paste(im1,((x - from_tile_x)*256, (-to_tile_y + y )*256,))
   out = out.crop(bbox)
   out = out.resize(size, Image.ANTIALIAS)
   out.save(file, "JPEG")  


if __name__ == '__main__':
  
  print getimg ("out.jpg",bbox, (width, height), layer)