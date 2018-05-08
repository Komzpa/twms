# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

try:
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps
except ImportError:
    import Image, ImageFilter, ImageEnhance, ImageOps

try:
  import numpy
  NUMPY_AVAILABLE = True
except ImportError:
  NUMPY_AVAILABLE = False
import datetime
from twms import getimg

try:
  import config

except:
  pass


def raster(result_img, filt, bbox = (-999,-999,999,9999), srs="EPSG:3857"):
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
      if ff == "swaprb":
        ii = result_img.split()
        result_img = Image.merge("RGBA", (ii[2],ii[1],ii[0],ii[3]))

     else:
      ff, tts = ff.split(":")
      try:
        tt = float(tts)
      except ValueError:
        tt = 1
        pass
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
      if ff == "fusion" and NUMPY_AVAILABLE:
        pix = numpy.array(result_img, dtype=int)
        a,b = result_img.size
        pan_img = getimg (bbox, srs, [b, a], config.layers[tts], datetime.datetime.now(), [])
        pan_img = pan_img.convert("L")
        print(pix.dtype)
        print(pix[...,1].shape)
        
        pan = numpy.array(pan_img)
        
        pix[...,0] = pix[...,0]*pan/(pix[...,0] + pix[...,1] + pix[...,2])
        pix[...,1] = pix[...,1]*pan/(pix[...,0] + pix[...,1] + pix[...,2])
        pix[...,2] = pix[...,2]*pan/(pix[...,0] + pix[...,1] + pix[...,2])

        print(pix.shape)
        result_img = Image.fromarray(numpy.uint8(pix))
        
        
        result_img = result_img.convert("RGBA")
    return result_img


