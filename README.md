# twms

Hacky TMS/WMS proxy for JOSM. Please use only allowed data sources for OpenStreetMap contributing.

* It's hard to proof which aerial imagery has been traced, but for a sake of OSM license purity use only approved [aerial imagery](https://wiki.openstreetmap.org/wiki/Aerial_imagery)
* Absolutely forbidden to copy from [copyrated](https://wiki.openstreetmap.org/wiki/Copyright) maps


## About this fork

* Consider it as hacky replacement for [MapProxy](https://wiki.openstreetmap.org/wiki/MapProxy)
* Tested for interoperability with [JOSM](https://josm.openstreetmap.de/), MapProxy, [SAS.Planet](http://www.sasgis.org/sasplaneta/)
* Few dependencies (only python-pillow is mandatory), [`http.server`](https://docs.python.org/3/library/http.server.html) is used instead of [webpy](https://webpy.org/)
* Huge refactoring: unsupported code has been [dropped](https://github.com/radioxoma/twms/commit/8a3a6bc6e562f5aeea480399c2bd00c345d34a12) (e.g. filters).
* SAS.Planet Time To Live (TTL), tile not exist `*.tne` file supported


## Services provided

* WMS 1.1.1 and 1.3.0 capabilities: `http://localhost:8080/wms?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0` supports tile links `http://localhost:8080/wms/{layer_id}/{z}/{x}/{y}{ext}` with reprojection.
* TileJSON 3.0.0 metadata: `http://localhost:8080/tilejson/{layer_id}.json`.
* WMTS 1.0.0 `http://127.0.0.1:8080/wmts/1.0.0/WMTSCapabilities.xml` provides a tile proxy without reprojection at `http://localhost:8080/wmts/{layer_id}/{z}/{x}/{y}{ext}`.
* Imagery overview web page http://localhost:8080 with JOSM [remote control](https://josm.openstreetmap.de/wiki/Help/RemoteControlCommands) (`wms`, `tms:`) links
    * Open "JOSM Imagery > Imagery preferences > Press *+TMS*, *Selected entries*" and paste link from here. E.g.: `tms:http://localhost:8080/wms/vesat/{z}/{x}/{y}.jpg`
* JOSM [imagery XML](https://josm.openstreetmap.de/wiki/Maps): http://localhost:8080/josm/maps.xml - imagery list for `imagery.layers.sites` property


## Setting up TWMS

Install dependencies and clone repo:

    $ sudo pacman -S python-pillow  # Packages for Archlinux
    $ git clone https://github.com/radioxoma/twms.git
    $ cd twms

Edit `twms/config.py` and set `tiles_cache` path to your `SAS.Planet/cache_ma/`. Run TWMS in terminal:

    $ python -m twms


## Shared "Slippy Map" cache

TWMS uses [Slippy map tilenames](https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames) cache in [MOBAC](https://mobac.sourceforge.io/) format i.e. filesystem with `{z}/{x}/{y}{ext}`.


### SAS.Planet

SAS.Planet works fine with [wine](https://www.winehq.org/). Open "Settings > Options > Cache tab > Set *Default cache type* to *Mobile atlas creator (MOBAC)*". So tile path will conform "Slippy Map" standard e.g. `SAS.Planet/cache_ma/vesat/{z}/{x}/{y}.jpg`. From now you can browse tiles and `*.tne` "tile not exists" files in SAS.Planet and share the same cache.

### MapProxy

MapProxy's quirks:

* Imposible to specify just one global relative 'directory' and use caches prefixes
* 'format' `image/jpg` for '*.jpg' and `image/jpeg` for '*.jpeg' file names

    caches:
      osmmapMapnik:
        grids: [GLOBAL_WEBMERCATOR]
        sources: [osm_tiles]
        cache:
          type: file
          directory_layout: tms
          directory: /home/rx/dev/gis/sasplanet/SAS.Planet/cache_ma/osmmapMapnik/
      vesat:
        grids: [GLOBAL_WEBMERCATOR]
        sources: [ve_tiles]
        format: image/jpg
        cache:
          type: file
          directory_layout: tms
          directory: /home/rx/dev/gis/sasplanet/SAS.Planet/cache_ma/vesat/


## Setting up JOSM

At 2021 JOSM uses [Java cache system](https://commons.apache.org/proper/commons-jcs/) ([ticket](https://josm.openstreetmap.de/ticket/11216)), which is not a directory with tiles, so it can't be shared. It also cannot be disabled in JOSM, so we move cache dir to RAM disk:

1. Set property 'imagery.generic.loader.cachedir' to `/dev/shm/JOSM/tiles` or start JOSM with parameter `-Djosm.cache=/dev/shm/JOSM/tiles`.
2. Set property 'imagery.cache.max_disk_size' to reasonable value, e.g. 64 Mb, to not exceed RAM


### Load tiles directly from disk

JOSM supports `file://` URL pointing to 256x256 tiles in EPSG:3857 projection (like OSM, Bing or Google, but not Yandex as it uses EPSG:3395). **So it's possible to make JOSM load tiles directly from SAS.Planet MOBAC cache, without running any server.**

1. Check [http://127.0.0.1:8080](http://127.0.0.1:8080) for available `file://` links
2. Open JOSM Imagery > Imagery preferences > Press *+TMS*, *Selected entries* and paste link. E.g.:

    tms:file:///home/user/dev/gis/sasplanet/SAS.Planet/cache_ma/vesat/{z}/{x}/{y}.jpg
    tms[18]:file:///c:/SAS.Planet/cache_ma/vesat/{z}/{x}/{y}.jpg  # Windows
