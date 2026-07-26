# twms

twms is a tiny web map service that connects the world of tiles and
the world of WMS.

The primary purpose of twms is to export raster tile sets to
WMS-enabled GIS applications. It can also act as a small tile proxy:
fetching remote tiles, keeping a filesystem cache, and serving that
cache back through WMS, WMTS, TileJSON, or direct slippy-map tile URLs.

twms intentionally stays small. The default server uses the Python
standard library, while the older `web.py` WSGI/standalone path is
still available for deployments that already use it.

## Install and run

Install from a checkout:

```sh
python -m pip install -e .
```

Run the default stdlib server:

```sh
twms 8080
```

or:

```sh
python -m twms 8080
```

The previous `web.py` server and WSGI adapter are still installed as:

```sh
twms-webpy
```

That path is kept for older deployments, including Windows/JOSM proxy
bundles that depended on `web.py`.

On GitHub, CI builds Windows executable artifacts for both entry points:

- `twms.exe`
- `twms-webpy.exe`

## Configuration

twms loads Python configuration from:

1. `/etc/twms/twms.conf`
2. the packaged `twms/twms.conf`
3. `twms.conf` in the current script directory

Important settings:

- `tiles_cache`: root directory for the filesystem tile cache
- `gpx_cache`: cache for downloaded OSM GPX traces
- `service_url`: externally visible base URL used in generated capabilities
- `default_layers`: layer list used when a request does not name layers
- `default_format`: output image MIME type, usually `image/jpeg`
- `layers`: configured imagery layers and their fetchers

Layer dictionaries usually define:

- `name`: human readable title
- `prefix`: cache subdirectory
- `ext`: tile extension such as `jpg` or `png`
- `proj`: tile pyramid projection, commonly `EPSG:3857` or `EPSG:3395`
- `remote_url`: upstream tile URL template
- `fetch`: fetcher function, normally `fetchers.Tile`
- `min_zoom` / `max_zoom`: optional zoom limits
- `cache_ttl`: optional fresh-cache lifetime in seconds
- `dead_tile`: optional dead-tile marker, either a legacy file path or a
  `{ "size": ..., "md5": {...} }` dictionary; dictionaries may also set
  `http_status` for an upstream status code that should be cached as `.tne`

## Client URLs

Assuming the server runs at `http://127.0.0.1:8080/`:

- overview page:
  `http://127.0.0.1:8080/`
- WMS 1.1.1/1.3.0 endpoint:
  `http://127.0.0.1:8080/`
- WMS capabilities:
  `http://127.0.0.1:8080/?service=WMS&request=GetCapabilities&version=1.3.0`
- WMTS capabilities:
  `http://127.0.0.1:8080/wmts/1.0.0/WMTSCapabilities.xml`
- TileJSON for a layer:
  `http://127.0.0.1:8080/tilejson/osm.json`
- direct tile URL:
  `http://127.0.0.1:8080/osm/{z}/{x}/{y}.png`
- WMTS REST tile URL:
  `http://127.0.0.1:8080/wmts/osm/{z}/{x}/{y}.png`

The legacy `GetTile` request is still supported because it is useful
when clients need filters or other TWMS-specific request parameters in
the tile URL:

```text
http://127.0.0.1:8080/?request=GetTile&layers=osm&z={z}&x={x}&y={y}&format=png
```

## QGIS

For WMS, create a WMS/WMTS connection pointing at:

```text
http://127.0.0.1:8080/
```

QGIS may request WMS 1.3.0 capabilities with uppercase parameter names
such as `SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0`; twms
accepts those. WMS 1.3.0 also accepts the `crs` parameter and advertises
`CRS:84` for lon/lat bounds, while the old WMS 1.1.1 capabilities keep
their existing `SRS` listings.

For WMTS, use:

```text
http://127.0.0.1:8080/wmts/1.0.0/WMTSCapabilities.xml
```

## JOSM

For a normal local proxy, add a TMS imagery entry such as:

```text
tms:http://127.0.0.1:8080/osm/{zoom}/{x}/{y}.png
```

For TWMS-specific parameters, use the WMS-style `GetTile` URL instead:

```text
tms:http://127.0.0.1:8080/?request=GetTile&layers=osm&z={zoom}&x={x}&y={y}&format=png
```

JOSM can also point directly at a compatible local slippy-map cache with
`file://` if no proxy or reprojection is needed:

```text
tms:file:///home/user/SAS.Planet/cache_ma/osm/{zoom}/{x}/{y}.png
```

On Windows the same idea uses a Windows path:

```text
tms:file:///C:/SAS.Planet/cache_ma/osm/{zoom}/{x}/{y}.png
```

## Shared tile caches

twms keeps the historical filesystem cache layout under `tiles_cache`:

```text
<tiles_cache>/<prefix>/z<z>/<x // 1024>/x<x>/<y // 1024>/y<y>.<ext>
```

Fresh cached tiles are served without network access. When `cache_ttl`
expires, twms tries to refresh the tile; if the remote fetch fails, the
stale cached tile can still be used. Missing/dead tiles can be recorded
as `.tne` files so repeated requests do not hammer upstream services.

This makes twms useful with tools that share a slippy-map/MOBAC-style
cache, including SAS.Planet and similar offline tile workflows.

## Optional dependencies

The base install keeps dependencies small:

- `Pillow`
- `web.py` for the legacy WSGI/standalone server path

Optional extras:

```sh
python -m pip install -e '.[proj]'
python -m pip install -e '.[cairo]'
```

`twms[proj]` enables pyproj-backed transformations for configured
non-core projections. Without it, twms still has built-in pure-Python
support for the common EPSG:4326/EPSG:3857/EPSG:3395 path.

`twms[cairo]` enables Cairo-backed vector rendering where the old
rendering path uses it.

## Credits

twms was originally written by Darafei Praliaskouski (Komzpa).
Andrew Shadura maintains Debian packaging and wrote the Debian manpage.
Eugene Dvoretsky (Radioxoma) contributed modernization work around
packaging, serving, caching, projections, documentation, and tile
protocols.

## TODO

- Make fetchers work with proxy.
- Full reprojection support.
- Imagery realignment.

## Conventions

- Inside twms, EPSG:4326 lon/lat should be used for transmitting
  coordinates.
