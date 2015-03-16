# Introduction #

> twms allows user who requests an image to post-filter it. This page describes a set of built-in filters.


# Details #

The following list of filters is supported:
  * **bw** - makes image colorless
  * **contour** - turns image into a set of colored contours (helps to save ink when printing maps)
  * **median** - does a median filtration for the image. Useful if image is post-processed later
  * **blur** - blurs image
  * **edge** - detect edges on image and make them sharper. Try in conjunction with **median** on aerial imagery if jpeg compression artifacts are visible
  * **brightness:x** - changes overall image brightness
  * **contrast:x** - changes overall image contrast
  * **sharpness:x** - changes overall image sharpness

Filters can be stacked and repeated multiple times to get desired effect, i.e. filter=median,edge,brightness:1.5

![http://wms.latlon.org/?layers=yhsat&filter=median,edge,brightness:1.5&param_for_gcode_wiki=.png](http://wms.latlon.org/?layers=yhsat&filter=median,edge,brightness:1.5&param_for_gcode_wiki=.png)
