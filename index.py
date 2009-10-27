# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFilter
import os
import math
import sys
import urllib
import config




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

    data = util.FieldStorage(req)
    gpx = data.get("gpx",None) 
    if not gpx:
     bbox = "27.6518898,53.8683186,27.6581944,53.8720359"
    else:
     bbox = None
    width = 0
    height = 0
    zoom = 18
    layer = ""
    req.content_type = "image/jpeg"
    if data.get("bbox",None) or bbox:
      bbox = tuple(map(float,data.get("bbox", bbox).split(",")))
    height = int(data.get("height",height))
    width = int(data.get("width",width))
    if (width > 2048) or (height > 2048):
      width = 1024
      height = 0
    if (width == 0) and (height == 0):
      width = 350
    layer = data.get("layer","osm")

    filt = data.get ("filter",None)
    rovarinfo = data.get ("rovar", None)
    print >> sys.stderr, req.get_remote_host(), layer, bbox, gpx, rovarinfo

    sys.stderr.flush()
    
    getimg(req,bbox, (height, width), layer, gpx, filt, rovarinfo)
    
    return apache.OK


#http://sat01.maps.yandex.net/tiles?l=sat&v=1.11.0&x=83812&y=42667&z=17
#http://sat01.maps.yandex.net/tiles?l=sat&v=1.11.0&x=83812&y=42668&z=17
#F:\home\kom\Downloads\SASPlanet\cache\yasat\z18\81\x83812\41\y42668.jpg




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


        FINETUNE_X = 24
        FINETUNE_Y=36

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
   for i in range (1,18):
     cx1, cy1, px1, py1 =  llz2txy (bbox[1],bbox[0], i, proj=config.layers[layer]["proj"])
     cx2, cy2, px2, py2 =  llz2txy (bbox[3],bbox[2], i, proj=config.layers[layer]["proj"])
     print ((cy1-cy2)*256+py1-py2), ((cx2-cx1)*256+px2-px1)
     if size[0] is not 0:
      if ((cx2-cx1)*256+px2-px1) >= size[0] :
       return i
     if size[1] is not 0:
      if ((cy1-cy2)*256+py1-py2) >= size[1]:
       return i

   return 18

def get_gpx_from_rovarinfo (id):
   import urllib2 
   import re
   route = urllib2.urlopen ("http://rovarinfo.rovarsoft.com/?q=route-display/%s"%id).read()
   rgexpr  = re.compile(r'LINESTRING\((.*)\)')
   line, = rgexpr.search(route).groups()
   coords = line.split(",")
   coords = [ [float(t) for t in x.split(" ")] for x in coords]
   coords = [(x[1],x[0]) for x in coords]
   return coords
   

   
   

def tile_image (layer, z, x, y, again=False, trybetter = True, real = False):
   """
   Returns asked image.
   again - is this a second pass on this tile?
   trybetter - should we try to combine this tile from better ones?
   real - should we return the tile even in not good quality?
   """
   local = config.tiles_cache + config.layers[layer]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
   ext = config.layers[layer]["ext"]
   gpt_image = False
   if not os.path.exists("/".join(local.split("/")[:-1])):
       os.makedirs("/".join(local.split("/")[:-1]))
   #print >> sys.stderr,layer, z, x, y, os.path.exists(local+"tne"), local+ext, real

   #sys.stderr.flush()
   if not os.path.exists(local+"tne") and not os.path.exists(local+"lock"):
    if os.path.exists(local+ext):			# First, look for tile in cache
      try:
	  im1 = Image.open(local+ext)
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
	im = Image.new("RGB", (512, 512))
	im1 = tile_image(layer, z+1,x*2,y*2)
        if im1:
	 im2 = tile_image(layer, z+1,x*2+1,y*2)
         if im2:  
	  im3 = tile_image(layer, z+1,x*2,y*2+1)
          if im3:
	    im4 = tile_image(layer, z+1,x*2+1,y*2+1)
            if im4:
	#     print >> sys.stderr,layer, z, x, y, again, " --- GLUED!"
        #     sys.stderr.flush()
	     im.paste(im1,(0,0))
	     im.paste(im2,(256,0))      
	     im.paste(im3,(0,256))     
	     im.paste(im4,(256,256))
	     im = im.resize((256,256),Image.ANTIALIAS)
	     im.save(local+"ups."+ext)
	     return im
    if not again:
     if config.layers[layer]["fetch"](z,x,y):    # Try fetching from outside
	return tile_image(layer,z,x,y,again=True)
   if real and (z>1): #config.layers[layer]["scalable"] and not trybetter:  # Try to cut image from worser
        if os.path.exists(local+"dsc."+ext):
            im = Image.open(local+"dsc."+ext)
            return im
	#print >> sys.stderr,layer, z, x, y, " --- downscaling"
        im = tile_image(layer, z-1, int(x/2), int(y/2),  again=False, trybetter=False, real=True)

        #sys.stderr.flush()
        #im = im.resize((512,512).ANTIALIAS)
        if im:
          im = im.crop((128 * (x % 2), 128 * (y % 2), 128 * (x % 2) + 128, 128 * (y % 2) + 128))
          im = im.resize((256,256), Image.ANTIALIAS)
          im.save(local+"dsc."+ext)
          #if not os.path.exists(local+"tne") and not os.path.exists(local+"lock")
          return im


def getimg (file, bbox, size, layer, gpx, filtr, rovarinfo):
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

   out = Image.new("RGB", (x, y))
   for x in range (from_tile_x, to_tile_x+1):
    for y in range (to_tile_y, from_tile_y+1):
     got_image = False
     im1 = tile_image (layer,zoom,x,y, real = True)
     if not im1:
        im1 = Image.new("RGB", (256, 256))
        imd = ImageDraw.Draw(im1)
        imd.line ([0,0,256,256],fill="#ff0000")
        imd.line ([0,255,255,255],fill="#fff000")

#         im1 = tile_image ("osm",zoom,x,y)
     out.paste(im1,((x - from_tile_x)*256, (-to_tile_y + y )*256,))     
   out = out.crop(bbox)   
   if (H == W) and (H == 0):
     W, H = out.size
   if H == 0:
     H = out.size[1]*W/out.size[0]
   if W == 0:
     W = out.size[0]*H/out.size[1]
   #out = out.filter(ImageFilter.SHARPEN)

   out = out.resize((W,H), Image.ANTIALIAS)
   #out = out.filter(ImageFilter.CONTOUR)
   if not filtr:
    filtr = "no"

   for ff in filtr.split(","):
    if ff == "bw" or ff == "yes":
     r,g,b = out.split()
     g = g.filter(ImageFilter.CONTOUR)
     outt = Image.merge ("RGB", (r,g,b))

     outt = Image.eval(out, lambda x: int((x+512)/3))
     outtbw = out.convert("L")    
    
    
    
     outtbw = outtbw.convert("RGB")
     out = Image.blend(outt, outtbw, 0.62)
    if ff == "edges":
      #r,g,b = out.split()
      #r = r.filter(ImageFilter.FIND_EDGES)
      #g = g.filter(ImageFilter.FIND_EDGES)
      #b = b.filter(ImageFilter.FIND_EDGES)
      #out = Image.merge ("RGB", (r,g,b))
      out = out.filter(ImageFilter.CONTOUR)
      #out = out.filter(ImageFilter.FIND_EDGES)
   
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
   out.save(file, "JPEG")  


if __name__ == '__main__':
  print getbestzoom ((27.404,53.829748,27.704,53.974),(0,300))

