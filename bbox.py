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
import sys


def point_is_in(bbox, point):
   """
   Checks whether point is in bbox
   """
   bbox = normalize(bbox)[0]
   
   return point[0]>=bbox[0] and point[0]<=bbox[2] and point[1]>=bbox[1] and point[1]<=bbox[3]

def bbox_is_in(bbox_outer, bbox_to_check, fully = True):
   """
   Checks whether bbox is inside outer
   """
   bo = normalize(bbox_outer)[0]
   bc = normalize(bbox_to_check)[0]
   if fully:
      return (bo[0]<=bc[0] and bo[2]>=bc[2]) and (bo[1]<=bc[1] and bo[3]>=bc[3])
   else:
      return ((bo[0]<=bc[0] and bo[2]>=bc[0]) or (bo[0]<=bc[2] and bo[2]>=bc[2])) and ((bo[1]<=bc[1] and bo[3]>=bc[1]) or (bo[1]<=bc[3] and bo[3]>=bc[3])) or ((bc[0]<=bo[0] and bc[2]>=bo[0]) or (bc[0]<=bo[2] and bc[2]>=bo[2])) and ((bc[1]<=bo[1] and bc[3]>=bo[1]) or (bc[1]<=bo[3] and bc[3]>=bo[3]))


def normalize (bbox):
   """
   Normalizes bbox order. Returns normalized bbox, and whether it was flipped on both axes.
   """

   flip_h = False
   flip_v = False
   bbox = list(bbox)
   while bbox[0] <= -180.:
        bbox[0] += 360.
        bbox[2] += 360.
   if bbox[0] > bbox[2]:
      bbox = (bbox[0],bbox[1],bbox[2]+360,bbox[3])
      #bbox = (bbox[2],bbox[1],bbox[0],bbox[3])
   if bbox[1] > bbox[3]:
      flip_h = True
      bbox = (bbox[0],bbox[3],bbox[2],bbox[1])
   
   
   print >> sys.stderr, bbox, "!!!"
   sys.stderr.flush()
   return bbox, flip_h, flip_v