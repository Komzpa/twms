# Configuration reference

TWMS loads Python configuration from:

1. `/etc/twms/twms.conf`
2. the packaged `twms/twms.conf`
3. `twms.conf` next to the running script

The packaged config is an example. Real deployments normally need local cache
paths, layer definitions, and service metadata.

## Common settings

- `debug`: enable more verbose diagnostics.
- `tiles_cache`: root directory for TWMS tile cache files.
- `install_path`: directory for packaged assets such as dead-tile samples.
- `gpx_cache`: cache directory for downloaded OSM GPX traces.
- `deadline`: seconds during which remote downloads are allowed before TWMS
  falls back to cached or lower-quality material.
- `upstream_timeout`: HTTP timeout for upstream tile/WMS requests.
- `upstream_retries` / `upstream_retry_delay`: retry budget for transient
  upstream network errors.
- `default_max_zoom`: default exclusive maximum zoom for layers that do not set
  their own `max_zoom`.
- `geometry_color`: default colors for WKT/GPX vector rendering.
- `linestring_width`: default rendered width for WKT/GPX lines.
- `default_layers`: comma-separated layer list used when a request omits
  `layers`; an empty value shows the overview page.
- `max_height` / `max_width`: maximum output image dimensions.
- `output_quality`, `output_progressive`, `output_optimize`: output image
  encoder options.
- `default_background`: background color for empty space.
- `default_vector_renderer`: `PIL` or `cairo`.
- `default_format`: output MIME type such as `image/jpeg`.

## Capabilities metadata

- `service_url`: public base URL used in generated WMS/WMTS/JOSM metadata.
- `wms_name`: service title.
- `default_bbox`: advertised lon/lat bounds.
- `contact_person`: metadata with `mail`, `real_name`, and `organization`.

## Layers

Each entry in `layers` describes one layer:

```python
layers = {
    "osm": {
        "name": "OpenStreetMap mapnik",
        "prefix": "osm",
        "ext": "png",
        "proj": "EPSG:3857",
        "fetch": "tms",
        "remote_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "transform_tile_number": lambda z, x, y: (z - 1, x, y),
        "scalable": False,
        "cache_ttl": 864000,
    },
}
```

Common layer keys:

- `name`: human-readable layer name.
- `prefix`: cache subdirectory.
- `ext` or `mimetype`: tile image type. `ext: "png"` and
  `mimetype: "image/png"` are equivalent after config normalization.
- `scalable`: allow TWMS to synthesize a lower zoom tile from higher zoom tiles.
- `proj`: tile pyramid projection, commonly `EPSG:3857`, `EPSG:3395`, or
  `EPSG:4326`.
- `min_zoom` / `max_zoom`: layer zoom bounds. `max_zoom` is historically
  exclusive. TileJSON output converts it to the inclusive `maxzoom` value that
  TileJSON clients expect.
- `empty_color` / `empty_color_delta`: color treated as transparent when an
  overlay layer is composited.
- `cache_ttl`: seconds during which cached tiles are fresh.
- `cached`: set to `False` for local or dynamic upstreams that should not be
  written into TWMS' tile cache.
- `cache_layout`: defaults to TWMS' historical grouped layout; `zxy`, `slippy`,
  `mobac`, or `tms` use `<tiles_cache>/<prefix>/<z>/<x>/<y>.<ext>`.
- `data_bounding_box`, `bounds`, or `bbox`: lon/lat layer bounds.
- `headers`: per-layer HTTP headers for upstream requests.
- `timeout`, `upstream_retries`, `upstream_retry_delay`: per-layer upstream
  request overrides.
- `layer_defaults`: optional top-level dictionary merged into every layer by
  the config loader.

## Fetchers

`fetch` may be a legacy callable or one of the readable aliases:

- `"tms"` / `"tile"` for tile URL sources.
- `"wms"` for WMS upstream sources.

Tile layers use:

- `remote_url`: legacy `%s` templates or readable placeholders such as `{z}`,
  `{x}`, `{y}`, `{-y}`, and `{q}`.
- `transform_tile_number`: optional function called as `(z, x, y)`.
- `dead_tile`: legacy file path or a dictionary with `size`, `md5`, and optional
  `http_status` for sparse datasets.

WMS upstream layers use:

- `remote_url`: a base GetMap URL. Legacy configs append `bbox`, `width`,
  `height`, and `srs`; readable templates may include `{bbox}`, `{width}`,
  `{height}`, and `{proj}`.
- `wms_proj`: projection requested from the upstream WMS if it differs from the
  layer projection.

## Response cache

`cache_tile_responses` maps direct `GetTile` responses to an existing
slippy-style cache:

```python
cache_tile_responses = {
    ("EPSG:3857", ("base",), (), 256, 256, (), "PNG"): (
        "/disk/base3857/",
        "png",
    ),
}
```

The key is:

```text
(projection, layers, filters, width, height, force, format)
```

Use empty tuples `()` for no filters and no force options. The canonical format
value is Pillow's format name (`"PNG"`, `"JPEG"`), although current TWMS also
accepts MIME keys such as `"image/png"` for compatibility with older examples.
