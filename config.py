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
import tilenames
import fetchers


debug = True

## Directory for tiles cache. 
tiles_cache = "/var/www/latlon/wms/cache/"

#known_projs = {
    #"EPSG:4326": pyproj.Proj("+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"),
    #"EPSG:3395":
       #"proj": '+proj=merc +lon_0=0 +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs',
       #"bounds":(-180,-85.0511287798,180,85.0511287798)
    #"EPSG:3857":{
       #"proj": '+proj=merc +lon_0=0 +lat_ts=0 +x_0=0 +y_0=0 +a=6378137 +b=6378137 +units=m +no_defs',
       #"bounds": (-180,-85.0511287798,180,85.0511287798)
 #},
    #"EPSG:900913": pyproj.Proj('+proj=merc +lon_0=0 +lat_ts=0 +x_0=0 +y_0=0 +a=6378137 +b=6378137 +units=m +no_defs')

#}





deadline = 45 # number of seconds that are given to make up image
service_url = "http://wms.play.latlon.org/"
wms_name = "latlon.org web map service"
default_bbox = (-180.0,-85.0511287798,180.0,85.0511287798)   # spherical mercator maximum. used for GetCapabilities
default_format = "image/jpeg"
contact_person = {
"mail": "",
"real_name": "",
"organization": ""
}

## Available layers. 
layers = {\
"DGsat": { \
     "name": "Digital Globe Satellite",
     "prefix": "DGsat",			# tile directory
     "ext": "jpg",			# tile images extension
     "scalable": True,			# could zN tile be constructed of four z(N+1) tiles
     "proj": 1,
},\
"yhsat": { \
     "name": "Yahoo Satellite",
     "prefix": "yhsat",			# tile directory
     "ext": "jpg",			# tile images extension
     "scalable": False,			# could zN tile be constructed of four z(N+1) tiles
     "fetch": fetchers.Tile,		# function that fetches given tile. should return None if tile wasn't fetched
     "remote_url": "http://aerial.maps.yimg.com/ximg?v=1.8&t=a&s=256&r=1&x=%s&y=%s&z=%s",
     "transform_tile_number": lambda z,x,y: (x,y,z-1),
     "dead_tile": "/var/www/latlon/wms/yahoo_nxt.jpg",
     "max_zoom": 18,
     "proj": 1,
},\
"yasat": { \
     "name": "Yandex Satellite",
     "prefix": "yasat",			# tile directory
     "ext": "jpg",			# tile images extension
     "scalable": False,			# could zN tile be constructed of four z(N+1) tiles
     "fetch": fetchers.Tile,	# function that fetches given tile. should return None if tile wasn't fetched
     "remote_url": "http://sat01.maps.yandex.net/tiles?l=sat&v=1.14.0&x=%s&y=%s&z=%s",
     "transform_tile_number": lambda z,x,y: (x,y,z-1),
     "dead_tile": "/var/www/latlon/wms/yandex_nxt.jpg",
     "proj": 2,
},\
"osm": { \
     "name": "OpenStreetMap mapnik",
     "prefix": "osm",			# tile directory
     "ext": "png",			# tile images extension
     "scalable": False,			# could zN tile be constructed of four z(N+1) tiles
     "fetch": fetchers.Tile,	# function that fetches given tile. should return None if tile wasn't fetched
     "remote_url": "http://c.tile.openstreetmap.org/%s/%s/%s.png",
     "transform_tile_number": lambda z,x,y: (z-1,x,y),
     "proj": 1,
     "cache_ttl": 86400,
},\
"irs":  { \
     "name": "Kosmosnimki.ru IRS Satellite",
     "prefix": "irs",                   # tile directory
     "ext": "jpg",                      # tile images extension
     "scalable": False,                 # could zN tile be constructed of four z(N+1) tiles
     "fetch": fetchers.Tile, # function that fetches given tile. should return None if tile wasn't fetched
     "remote_url": "http://maps.kosmosnimki.ru/TileSender.ashx?ModeKey=tile&MapName=F7B8CF651682420FA1749D894C8AD0F6&LayerName=950FA578D6DB40ADBDFC6EEBBA469F4A&z=%s&x=%s&y=%s",
     "transform_tile_number": lambda z,x,y: (z-1,int(-((int(math.pow(2,z-1)))/ 2)+x),int(-((int(math.pow(2,z-1)))/ 2)+ int(math.pow(2,z-1)-(y+1)))),
     "dead_tile": "/var/www/latlon/wms/irs_nxt.jpg",
     "max_zoom": 16,
     "proj": 2,
},\
"SAT":  { \
     "name": "Google Satellite Partial",
     "prefix": "SAT",                   # tile directory
     "ext": "jpg",                      # tile images extension
     "scalable": True,                 # could zN tile be constructed of four z(N+1) tiles
     "max_zoom": 19,
     "proj": 1,
},\
"navitel":  { \
     "name": "Navitel Navigator Maps",
     "prefix": "Navitel",                   # tile directory
     "ext": "png",                      # tile images extension
     "scalable": False,                 # could zN tile be constructed of four z(N+1) tiles
     "fetch": fetchers.Tile, # function that fetches given tile. should return None if tile wasn't fetched
     "remote_url": "http://map.navitel.su/navitms.fcgi?t=%08i,%08i,%02i",
     "transform_tile_number": lambda z,x,y: (x, 2**(z-1)-y-1, z-1),
     "proj": 1,
},\
"gshtab":  { \
     "name": "Genshtab 100k maps of Belarus",
     "prefix": "gshtab",                   # tile directory
     "ext": "png",                      # tile images extension
     "scalable": False,                 # could zN tile be constructed of four z(N+1) tiles
     "fetch": fetchers.Wms4326as3857, # function that fetches given tile. should return None if tile wasn't fetched
     "wms_4326": "http://wms.latlon.org/cgi-bin/ms?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=GS-100k-N-34,GS-100k-N-35,GS-100k-N-36&STYLES=&SRS=EPSG:4326&FORMAT=image/png&",
     "max_zoom": 16,
     "proj": 1,
},\

}
