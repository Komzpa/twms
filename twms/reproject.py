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

import Image
import projections
import sys

def reproject(image, bbox, srs_from, srs_to):
    out = image.copy()
    op = out.load()
    il = image.load()
    bbox_from = projections.from4326(bbox, srs_from)
    bbox_to = projections.from4326(bbox, srs_to)
    width, height = image.size
    
    for x in range(0,width):
      for y in range(0,height):
         dx = ((1.*x/width)*(bbox_to[2]-bbox_to[0]))+bbox_to[0]
         dy = ((1.*y/height)*(bbox_to[3]-bbox_to[1]))+bbox_to[1]
         #print >> sys.stderr, x, dx, y, dy
         dx,dy = tuple(projections.transform([dx,dy], srs_to, srs_from))
         
         dx = width*(dx - bbox_from[0])/(bbox_from[2]-bbox_from[0])
         dy = height*(dy - bbox_from[1])/(bbox_from[3]-bbox_from[1])
         op[x,y] = il[int(dx),int(dy)]

         #sys.stderr.flush()
    return out



