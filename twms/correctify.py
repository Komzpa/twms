# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://www.wtfpl.net/ for more details.

#import sys
import projections
import os
import config


distance = lambda z,x,y,g: ((z-y)**2+(x-g)**2)**(0.5)

def has_corrections(layer):
  corrfile = config.tiles_cache + layer.get("prefix", "")+ "/rectify.txt"
  return os.path.exists(corrfile)

def corr_wkt(layer):
  corrfile = config.tiles_cache + layer.get("prefix", "")+ "/rectify.txt"
  corr = open(corrfile, "r")
  wkt = ""
  for line in corr:
    d,c,b,a,user,ts = line.split()
    d,c,b,a = (float(d),float(c),float(b),float(a))
    wkt +="POINT(%s %s),LINESTRING(%s %s,%s %s),"%(d,c,d,c,b,a)
  return wkt[:-1]
  

def rectify(layer, point):
    corrfile = config.tiles_cache + layer.get("prefix", "")+ "/rectify.txt"
    srs = layer["proj"]
    if not os.path.exists(corrfile):
       return point
    corr = open(corrfile, "r")
    lons, lats = point
    loni, lati, lona, lata = projections.projs[projections.proj_alias.get(srs,srs)]["bounds"]
    if (lons is loni and lats is lati) or (lons is lona and lats is lata):
      return point
    #print >> sys.stderr, pickle.dumps(coefs[layer])
#    sys.stderr.flush()
    lonaz, loniz, lataz, latiz = lona, loni, lata, lati
    maxdist = (1.80)
    for line in corr:
       d,c,b,a,user,ts = line.split()
       d,c,b,a = (float(d),float(c),float(b),float(a))
    #for d,c,b,a in coefs[layer]:
      # print >> sys.stderr, a,b, distance(lons, lats, b, a)
       if distance(b,a, lons, lats) < maxdist:
        if a > lats:
          if distance(a,b,lats,lons) <= distance(lata,lona,lats,lons):
            lata = a
            lataz = c
        if a < lats:
          if distance(a,b,lats,lons) <= distance(lati,loni,lats,lons):
            lati = a
            latiz = c
        if b > lons:
          if distance(a,b,lats,lons) <= distance(lata,lona,lats,lons):
            lona = b
            lonaz = d
        if b < lons:
          if distance(a,b,lats,lons) <= distance(lati,loni,lats,lons):
            loni = b
            loniz = d
#    print >> sys.stderr, loni, lati, lona, lata, distance(loni, lati, lona, lata)
#    print >> sys.stderr, "clat:", (lata-lati)/(lataz-latiz), (lona-loni)/(lonaz-loniz)
#    sys.stderr.flush()

    lons, lats = projections.from4326(point, srs)
    lona, lata = projections.from4326((lona,lata), srs)
    loni, lati = projections.from4326((loni,lati), srs)
    lonaz, lataz = projections.from4326((lonaz,lataz), srs)
    loniz, latiz = projections.from4326((loniz,latiz), srs)


    latn = (lats-lati)/(lata-lati)
    latn = (latn * (lataz-latiz))+latiz
    lonn = (lons-loni)/(lona-loni)
    lonn = (lonn * (lonaz-loniz))+loniz
       
    return projections.to4326((lonn,latn), srs)
       
#print rectify("yasat", (27.679068, 53.885122), "")
def r_bbox(layer, bbox):
    corrfile = config.tiles_cache + layer.get("prefix", "")+ "/rectify.txt"
    srs = layer["proj"]
    if not os.path.exists(corrfile):
       return bbox
    a,b,c,d = projections.from4326(bbox,srs)
    cx, cy = (a+c)/2, (b+d)/2
    cx1,cy1 = projections.from4326(rectify(layer,projections.to4326((cx,cy), srs)),srs)
    a1,b1 = projections.from4326(rectify(layer,projections.to4326((a,b), srs)),srs)
    c1,d1 = projections.from4326(rectify(layer,projections.to4326((c,d), srs)),srs)
    
    dx,dy = ((cx1-cx)+(a1-a)+(c1-c))/3, ((cy1-cy)+(b1-b)+(d1-d))/3
#    print >> sys.stderr, dx,dy
#    sys.stderr.flush()
    return projections.to4326((a+dx,b+dy,c+dx,d+dy),srs)
    
