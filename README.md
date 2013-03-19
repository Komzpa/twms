About
=====

twms is a script that connects World of Tiles and World of WMS.
The name ‘twms’ stands for twms web map server.

The primary purpose of twms is to export your map tiles to the
WMS-enabled applications.

twms can export a set of raster tiles as a WMS service
so GIS applications that support WMS protocol can access
this tile set. Also, twms can act as a proxy and perform
WMS requests to external services and serve the tile cache

TODO
====

 - Make fetchers work with proxy
 - Full reprojection support
 - Imagery realignment

Conventions
===========

 - Inside tWMS, only EPSG:4326 latlon should be used for transmitting coordinates.
