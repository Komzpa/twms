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

Optional launcher templates are shipped under `share/twms/contrib`:

- `twms.bat` starts `python -m twms` minimized for small Windows/JOSM proxy
  deployments.
- `twms.desktop` is a simple terminal desktop-entry template for Linux
  desktops or downstream packages.

## Configuration

twms loads Python configuration from:

1. `/etc/twms/twms.conf`
2. the packaged `twms/twms.conf`
3. `twms.conf` in the current script directory

The old Google Code wiki documentation is now kept in this repository under
[`docs/`](docs/index.md), including an expanded configuration reference,
installation notes, and filter documentation.

Important settings:

- `tiles_cache`: root directory for the filesystem tile cache
- `gpx_cache`: cache for downloaded OSM GPX traces
- `service_url`: externally visible base URL used in generated capabilities
- `upstream_timeout`: default upstream HTTP timeout in seconds; the example
  config uses 30 seconds so threaded servers do not wait forever on a stalled
  tile source
- `upstream_retries` / `upstream_retry_delay`: optional retry budget for
  transient upstream network errors. The default is one attempt, preserving the
  historical no-retry behavior; layers can opt in with their own values.
- `default_layers`: layer list used when a request does not name layers
- `default_format`: output image MIME type, usually `image/jpeg`
- `layers`: configured imagery layers and their fetchers

Layer dictionaries usually define:

- `name`: human readable title
- `prefix`: cache subdirectory
- `ext`: tile extension such as `jpg` or `png`
- `proj`: tile pyramid projection, commonly `EPSG:3857` or `EPSG:3395`
- `remote_url`: upstream tile/WMS URL template; legacy tile `%s/%s/%s`
  templates still work, named tile placeholders `{z}`, `{x}`, `{y}`, `{-y}`,
  and `{q}` are accepted for readable Slippy/TMS/Bing URLs, and WMS upstream
  templates may use `{bbox}`, `{width}`, `{height}`, and `{proj}`
- `headers`: optional upstream HTTP request headers, such as `Referer`,
  `User-Agent`, or authentication cookies required by a particular source
- `fetch`: fetcher function, normally `fetchers.Tile`; readable aliases
  `"tms"` / `"tile"` and `"wms"` are also accepted
- `timeout`: optional per-layer upstream HTTP timeout in seconds; set to
  `None` only if an old deployment deliberately wants the historical unbounded
  wait
- `upstream_retries` / `upstream_retry_delay`: optional per-layer retry
  override for temporary network failures. HTTP errors such as 404 are still
  handled by the cache/TNE rules instead of being retried as generic transport
  failures.
- `min_zoom` / `max_zoom`: optional zoom limits
- `cache_ttl`: optional fresh-cache lifetime in seconds
- `cache_layout`: optional cache path layout; the default is TWMS'
  historical grouped layout, while `zxy` stores slippy/MOBAC-style
  `<tiles_cache>/<prefix>/<z>/<x>/<y>.<ext>` tiles
- `dead_tile`: optional dead-tile marker, either a legacy file path or a
  `{ "size": ..., "md5": {...} }` dictionary; dictionaries may also set
  `http_status` for an upstream status code that should be cached as `.tne`

TWMS intentionally does not read browser cookie stores automatically. If a
private deployment needs a short-lived cookie, copy it into the layer `headers`
or load it from your own local config code so the server does not gain a
browser-profile dependency.

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

JOSM can also consume the generated imagery list:

```text
http://127.0.0.1:8080/josm/imagery.xml
```

The generated list includes configured layer bounds, zoom limits, overlays,
attribution URLs, and known no-tile MD5 checksums when those are present.

For TWMS-specific parameters, use the WMS-style `GetTile` URL instead:

```text
tms:http://127.0.0.1:8080/?request=GetTile&layers=osm&z={zoom}&x={x}&y={y}&format=png
```

JOSM can also point directly at a compatible local slippy-map cache with
`file://` if no proxy or reprojection is needed. Configure that layer with
`cache_layout: "zxy"` so TWMS uses the same `<z>/<x>/<y>` path:

```text
tms:file:///home/user/SAS.Planet/cache_ma/osm/{zoom}/{x}/{y}.png
```

On Windows the same idea uses a Windows path:

```text
tms:file:///C:/SAS.Planet/cache_ma/osm/{zoom}/{x}/{y}.png
```

## Shared tile caches

By default, twms keeps the historical filesystem cache layout under
`tiles_cache`:

```text
<tiles_cache>/<prefix>/z<z>/<x // 1024>/x<x>/<y // 1024>/y<y>.<ext>
```

Fresh cached tiles are served without network access. When `cache_ttl`
expires, twms tries to refresh the tile; if the remote fetch fails, the
stale cached tile can still be used. Missing/dead tiles can be recorded
as `.tne` files so repeated requests do not hammer upstream services.

Layers that need to share a slippy-map/MOBAC-style cache, including
SAS.Planet and similar offline tile workflows, can opt in with
`cache_layout: "zxy"`:

```text
<tiles_cache>/<prefix>/<z>/<x>/<y>.<ext>
```

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
