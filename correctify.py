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

#import sys
import projections
import os
import config


distance = lambda z,x,y,g: ((z-y)**2+(x-g)**2)**(0.5)

def rectify(layer, point, srs):
    corrfile = config.tiles_cache + config.layers[layer].get("prefix", "")+ "/rectify.txt"
    if not os.path.exists(corrfile):
       return point
    corr = open(corrfile, "r")
    lons, lats = point
    loni, lati, lona, lata = projections.projs[projections.proj_alias.get(srs,srs)]["bounds"]
    #print >> sys.stderr, pickle.dumps(coefs[layer])
#    sys.stderr.flush()
    lonaz, loniz, lataz, latiz = lona, loni, lata, lati
    maxdist = (0.5)
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
def r_bbox(layer, bbox, srs):
    corrfile = config.tiles_cache + config.layers[layer].get("prefix", "")+ "/rectify.txt"
    if not os.path.exists(corrfile):
       return bbox
    a,b,c,d = projections.from4326(bbox,srs)
    cx, cy = (a+c)/2, (b+d)/2
    cx1,cy1 = projections.from4326(rectify(layer,projections.to4326((cx,cy), srs),srs),srs)
    a1,b1 = projections.from4326(rectify(layer,projections.to4326((a,b), srs),srs),srs)
    c1,d1 = projections.from4326(rectify(layer,projections.to4326((c,d), srs),srs),srs)
    
    dx,dy = ((cx1-cx)+(a1-a)+(c1-c))/3, ((cy1-cy)+(b1-b)+(d1-d))/3
#    print >> sys.stderr, dx,dy
#    sys.stderr.flush()
    return projections.to4326((a+dx,b+dy,c+dx,d+dy),srs)
    