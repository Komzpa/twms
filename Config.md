# Common things #

  * **debug** _boolean_ - if True, TWMS will probably be more verbose than usually
  * **tiles\_cache** _string_ - path where tiles cache in tWMS format is accessible
  * **install\_path** _string_ - path to different stuff shipped with tWMS, like broken tile samples and so on
  * **gpx\_cache** _string_ - path to directory where tWMS should store OSM gpx files cache if asked to render
  * **deadline** _float_ - number of seconds when outer downloads are permitted. After that number image is constructed of what is alreade in cache. Useful for programs like QGIS which have 60-second WMS timeout
  * **default\_max\_zoom** _int_ - default value of max\_zoom. Can be overridden per-layer.
  * **geometry\_color** _dict_ - colors that WKT renderer should use to render each geometry. contains "GEOMETRY\_TYPE": "_PIL color string_", pairs;

  * **default\_layers** _string_ - default value for LAYERS= request string. If empty, overview HTML page is shown.
  * **max\_height** _int_ maximal allowed requested height
  * **max\_width** _int_ maximal allowed requested width
  * **output\_quality** _int_ - output image compression quality (matters for JPEG)
  * **output\_progressive** _bool_ - should image be progressive? (matters for JPEG)
  * **output\_optimize** _bool_ - should image be optimized? (matters for PNG)
  * **default\_background** _PIL color string_ - default background color for empty space
  * **default\_vector\_renderer** _string_ - what library to use for vector rasterization - "cairo" or "PIL"
  * **default\_format** _string_ - default image MIME-type, like "image/jpeg"
# stuff used for GetCapabilities #
  * **service\_url** _string_ - base URL service installed at
  * **wms\_name** _string_ - name of WMS service
  * **default\_bbox** _4326-bbox tuple_ - area to which service should be announced to restricted
  * **contact\_person** _dict_ - info about whom to contact
    * **mail** _string_ - announced e-mail
    * **real\_name** _string_ - announced admin's real name
    * **organization** _string_ - announced service owner organization


# Layers description #

All accessible layers should be mentioned in **layers** _dict_ in format "Layer\_name": {_describing dict_}

Available _describing dict_ options:
  * **name** _string_ - visible layer name
  * **prefix** _string_ - cache tile subdirectory name
  * **ext** _string_ - tile image files extension
  * **scalable** _bool_ - if True, tWMS will try to construct tile of better ones if they are available (better for home use and satellite images, or scanned maps). If False, tWMS will use nearest zoom level (better for rasterized vector maps and production servers)
  * **proj** _string_ - EPSG code of layer tiles projection.
  * **min\_zoom** _int_ - the worst zoom level number service provides
  * **max\_zoom** _int_ - the best zoom level number service provides
  * **empty\_color** _PIL color string_ - if this layer is overlayed over another, this color will be considered transparent. Also used for dead tile detection in **fetchers.WMS**
  * **cache\_ttl** _sencons_ - time that cache will be considered valid
  * **cached** _bool_ - if False, layer won't be cached. Good in combinations with local WMS or tile services to add tWMS features to them
  * **data\_bounding\_box** _4326-bbox tuple_ - no fetching will be performed outside this bbox. Good when caching just one country or a single satellite image.
  * **fetch** _function (z, x, y, layer\_dict)_ - function that fetches given tile. should return None if tile wasn't fetched.

> tWMS has a number of pre-written fetchers:
    * **fetchers.Tile** - designed for services that provide images over tile protocol, like http://kosmosnimki.ru or http://maps.yahoo.com. Uses following parameters from layer dict:
      * **remote\_url** _string_ - Base tiles URL. May contain python placeholders like "%s"
      * **transform\_tile\_number** _function (x, y, z)_ - function (usually lambda) that returns tuple that will be substituted into **remote\_url**. If omitted, (z,x,y) tuple is used.
      * **dead\_tile** _filename_ - file which contains broken (empty) tile for this service. If server responds with this data, it will not be saved into cache; negative mark will be saved instead.
    * **fetchers.WMS**
      * **remote\_url** _string_ - Base WMS URL. A GetMap request with omitted srs, height, width and bbox. Should probably end in "?" or "&".
      * **wms\_proj** _string_ - what projection to use when asking images from WMS. Note that images probably won't be properly reprojected if it differs from **proj**. Helps to cope with broken WMS services.