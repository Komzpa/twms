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


import ImageFilter
import ImageEnhance
import ImageOps

def raster(result_img, filt):
    """
    Applies various filters to image.
    """
    for ff in filt:
     if ff.split(":") == [ff,]:
      if ff == "bw":
       result_img = result_img.convert("L")
       result_img = result_img.convert("RGBA")

      if ff == "contour":
        result_img = result_img.filter(ImageFilter.CONTOUR)
      if ff == "median":
        result_img = result_img.filter(ImageFilter.MedianFilter(5))
      if ff == "blur":
        result_img = result_img.filter(ImageFilter.BLUR)
      if ff == "edge":
        result_img = result_img.filter(ImageFilter.EDGE_ENHANCE)
      if ff == "equalize":
        result_img = result_img.convert("RGB")
        result_img = ImageOps.equalize(result_img)
        result_img = result_img.convert("RGBA")
      if ff == "autocontrast":
        result_img = result_img.convert("RGB")
        result_img = ImageOps.autocontrast(result_img)
        result_img = result_img.convert("RGBA")

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
      if ff == "autocontrast":
        result_img = result_img.convert("RGB")
        result_img = ImageOps.autocontrast(result_img, tt)
        result_img = result_img.convert("RGBA")
    return result_img


