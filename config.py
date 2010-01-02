# -*- coding: utf-8 -*-

import urllib
import filecmp
import time
import os
import math
import sys


## Directory for tiles cache. 
tiles_cache = "/var/www/latlon/wms/cache/"
#localTile = lambda z,x,y: tiles_cache+"/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)

def FetchYandex (z,x,y):
   yh_dead_tile = "/var/www/latlon/wms/yandex_nxt.jpg"
   remote = "http://sat01.maps.yandex.net/tiles?l=sat&v=1.14.0&x=%s&y=%s&z=%s"%(x,y,z-1)
   local = tiles_cache + layers["yasat"]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
   if not os.path.exists("/".join(local.split("/")[:-1])):
       os.makedirs("/".join(local.split("/")[:-1]))
   print >> sys.stderr, z, x, y,  " --- yaNDoo is fetching"
   sys.stderr.flush()
   try:
    os.mkdir(local+"lock")
   except OSError:
    return None
   urllib.urlretrieve (remote, local+ layers["yasat"]["ext"])
   os.rmdir(local+"lock")
   if not os.path.exists(local+ layers["yasat"]["ext"]):
      print >> sys.stderr, z, x, y,  " --- yahhoo unfetched, strange"
      sys.stderr.flush()
      return False
   if filecmp.cmp(local+layers["yasat"]["ext"], yh_dead_tile):
    #  print >> sys.stderr, z, x, y,  " --- yahhoo dead :("
    #  sys.stderr.flush()
      tne = open (local+"tne", "w")
      when = time.localtime()
      tne.write("%02d.%02d.%04d %02d:%02d:%02d"%(when[2],when[1],when[0],when[3],when[4],when[5]))
      tne.close()
      os.remove(local+ layers["yasat"]["ext"])
      return False
   return local+layers["yasat"]["ext"]


def FetchYahoo (z,x,y):
   yh_dead_tile = "/var/www/latlon/wms/yahoo_nxt.jpg"
   remote = "http://aerial.maps.yimg.com/ximg?v=1.8&t=a&s=256&r=1&x=%s&y=%s&z=%s"%(x,((2**(z-1)/2)-1)-y,z)
   local = tiles_cache + layers["yhsat"]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
   if not os.path.exists("/".join(local.split("/")[:-1])):
       os.makedirs("/".join(local.split("/")[:-1]))
   #print >> sys.stderr, z, x, y,  " --- yahhoo is fetching"
   #sys.stderr.flush()
   try:
    os.mkdir(local+"lock")
   except OSError:
    return None
   urllib.urlretrieve (remote, local+ layers["yhsat"]["ext"])
   os.rmdir(local+"lock")
   if not os.path.exists(local+ layers["yhsat"]["ext"]):
      print >> sys.stderr, z, x, y,  " --- yahhoo unfetched, strange"
      sys.stderr.flush()
      return False
   if filecmp.cmp(local+layers["yhsat"]["ext"], yh_dead_tile):
    #  print >> sys.stderr, z, x, y,  " --- yahhoo dead :("
    #  sys.stderr.flush()
      tne = open (local+"tne", "w")
      when = time.localtime()
      tne.write("%02d.%02d.%04d %02d:%02d:%02d"%(when[2],when[1],when[0],when[3],when[4],when[5]))
      tne.close()
      os.remove(local+ layers["yhsat"]["ext"])
      return False
   return local+layers["yhsat"]["ext"]

def FetchOsm (z,x,y):
          osm_url = "http://c.tile.openstreetmap.org/%s/%s/%s.png" % (z-1, x, y)
          local_url = tiles_cache + layers["osm"]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y) + layers["osm"]["ext"]
	  if not os.path.exists("/".join(local_url.split("/")[:-1])):
            os.makedirs("/".join(local_url.split("/")[:-1]))
          urllib.urlretrieve (osm_url, local_url)
          return local_url
          
def FetchNavitel (z,x,y):
          osm_url = "http://map.navitel.su/navitms.fcgi?t=%08i,%08i,%02i" % (x, 2**(z-1)-y-1, z-1)
          local_url = tiles_cache + layers["navitel"]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y) + layers["navitel"]["ext"]
          if not os.path.exists("/".join(local_url.split("/")[:-1])):
            os.makedirs("/".join(local_url.split("/")[:-1]))
          urllib.urlretrieve (osm_url, local_url)
          return local_url
          



def FetchIrs (z,x,y):
   yh_dead_tile = "/var/www/latlon/wms/irs_nxt.jpg"
   if z >= 16:
       return None
   tx = int(-((int(math.pow(2,z-1)))/ 2)+x)
   ty = int(-((int(math.pow(2,z-1)))/ 2)+ int(math.pow(2,z-1)-(y+1)))

   remote = "http://maps.kosmosnimki.ru/TileSender.ashx?ModeKey=tile&MapName=Kosmosnimki&LayerName=F7B8CF651682420FA1749D894C8AD0F6&z=%s&x=%s&y=%s"%(z-1,tx,ty)
   remote = "http://maps.kosmosnimki.ru/TileSender.ashx?ModeKey=tile&MapName=F7B8CF651682420FA1749D894C8AD0F6&LayerName=950FA578D6DB40ADBDFC6EEBBA469F4A&z=%s&x=%s&y=%s"%(z-1,tx,ty)
   local = tiles_cache + layers["irs"]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y)
   if not os.path.exists("/".join(local.split("/")[:-1])):
       os.makedirs("/".join(local.split("/")[:-1]))
   print >> sys.stderr,remote, z, x, y,  " --- IRS is fetching"
   sys.stderr.flush()
   try:
    os.mkdir(local+"lock")
   except OSError:
    return None
   urllib.urlretrieve (remote, local+ layers["irs"]["ext"])
   os.rmdir(local+"lock")
   if not os.path.exists(local+ layers["irs"]["ext"]):
      print >> sys.stderr, z, x, y,  " --- IRS unfetched, strange"
      sys.stderr.flush()
      return False
   if filecmp.cmp(local+layers["irs"]["ext"], yh_dead_tile):
  #    print >> sys.stderr, z, x, y,  " --- IRS dead :("
  #    sys.stderr.flush()
  #    tne = open (local+"tne", "w")
  #    when = time.localtime()
  #    tne.write("%02d.%02d.%04d %02d:%02d:%02d"%(when[2],when[1],when[0],when[3],when[4],when[5]))
  #    tne.close()
      os.remove(local+ layers["irs"]["ext"])
      return False
   return local+layers["irs"]["ext"]
#def FetchIrs (z,x,y):
          #if z > 15:
             #return None
          #print >> sys.stderr, z, x, y,  " --- yahhoo dead :("
          #sys.stderr.flush()

          #osm_url = "http://maps.kosmosnimki.ru/TileSender.ashx?ModeKey=tile&MapName=Kosmosnimki&LayerName=C9458F2DCB754CEEACC54216C7D1EB0A&z=%s&x=%s&y=%s" % (z-1, x, y)
          #local_url = tiles_cache + layers["irs"]["prefix"] + "/z%s/%s/x%s/%s/y%s."%(z, x/1024, x, y/1024,y) + layers["irs"]["ext"]
          #if not os.path.exists("/".join(local_url.split("/")[:-1])):
            #os.makedirs("/".join(local_url.split("/")[:-1]))
          #urllib.urlretrieve (osm_url, local_url)
          #return local_url


## Available layers. 


layers = {\
"DGsat": { \
     "name": "Digital Globe Satellite",
     "prefix": "DGsat",			# tile directory
     "ext": "jpg",			# tile images extension
     "scalable": True,			# could zN tile be constructed of four z(N+1) tiles
     "fetch": lambda z,x,y: None,	# function that fetches given tile. should return None if tile wasn't fetched
     "proj": 1,
},\
"yhsat": { \
     "name": "Yahoo Satellite",
     "prefix": "yhsat",			# tile directory
     "ext": "jpg",			# tile images extension
     "scalable": True,			# could zN tile be constructed of four z(N+1) tiles
     "fetch": FetchYahoo,		# function that fetches given tile. should return None if tile wasn't fetched
     "proj": 1,
},\
"yasat": { \
     "name": "Yandex Satellite",
     "prefix": "yasat",			# tile directory
     "ext": "jpg",			# tile images extension
     "scalable": True,			# could zN tile be constructed of four z(N+1) tiles
     "fetch": FetchYandex,	# function that fetches given tile. should return None if tile wasn't fetched
     "proj": 2,
},\
"yasat_noscale": { \
     "name": "Yandex Satellite (unscaled tiles)",
     "prefix": "yasat",			# tile directory
     "ext": "jpg",			# tile images extension
     "scalable": False,			# could zN tile be constructed of four z(N+1) tiles
     "fetch": FetchYandex,	# function that fetches given tile. should return None if tile wasn't fetched
     "proj": 2,
},\
"osm": { \
     "name": "OpenStreetMap mapnik",
     "prefix": "osm",			# tile directory
     "ext": "png",			# tile images extension
     "scalable": False,			# could zN tile be constructed of four z(N+1) tiles
     "fetch": FetchOsm,	# function that fetches given tile. should return None if tile wasn't fetched
     "proj": 1,
},\
"irs":  { \
     "name": "Kosmosnimki.ru IRS Satellite",
     "prefix": "irs",                   # tile directory
     "ext": "jpg",                      # tile images extension
     "scalable": False,                 # could zN tile be constructed of four z(N+1) tiles
     "fetch": FetchIrs, # function that fetches given tile. should return None if tile wasn't fetched
     "proj": 2,
},\
"irs_failsafe":  { \
     "name": "Kosmosnimki.ru IRS Satellite - failsafe mode",
     "prefix": "irs",                   # tile directory
     "ext": "jpg",                      # tile images extension
     "scalable": True,                 # could zN tile be constructed of four z(N+1) tiles
     "fetch": lambda z,x,y: None, # function that fetches given tile. should return None if tile wasn't fetched
     "proj": 2,
},\
"irs_hq":  { \
     "name": "Kosmosnimki.ru IRS Satellite",
     "prefix": "irs",                   # tile directory
     "ext": "jpg",                      # tile images extension
     "scalable": True,                 # could zN tile be constructed of four z(N+1) tiles
     "fetch": FetchIrs, # function that fetches given tile. should return None if tile wasn't fetched
     "proj": 2,
},\
"SAT":  { \
     "name": "Google Satellite Partial",
     "prefix": "SAT",                   # tile directory
     "ext": "jpg",                      # tile images extension
     "scalable": True,                 # could zN tile be constructed of four z(N+1) tiles
     "fetch": lambda z,x,y: None, # function that fetches given tile. should return None if tile wasn't fetched
     "proj": 1,
},\
"navitel":  { \
     "name": "Navitel Navigator Maps",
     "prefix": "Navitel",                   # tile directory
     "ext": "png",                      # tile images extension
     "scalable": True,                 # could zN tile be constructed of four z(N+1) tiles
     "fetch": FetchNavitel, # function that fetches given tile. should return None if tile wasn't fetched
     "proj": 1,
},\
}
