# Filters

TWMS lets clients post-process rendered images with the `filter`/`filt`
request parameter. Filters can be stacked and repeated:

```text
filter=median,edge,brightness:1.5
```

Built-in filters:

- `bw`: convert to grayscale.
- `contour`: render colored contours, useful for printing.
- `median`: median filter, useful before other image processing.
- `blur`: blur the image.
- `edge`: detect and sharpen edges. This can help with compressed aerial
  imagery, especially with `median`.
- `brightness:x`: adjust brightness.
- `contrast:x`: adjust contrast.
- `sharpness:x`: adjust sharpness.
- `swaprb`: swap red and blue channels for sources with channel-order issues.

For tile clients that cannot send arbitrary WMS parameters, keep using the
legacy `GetTile` endpoint so the filter list can live in the tile URL:

```text
http://127.0.0.1:8080/?request=GetTile&layers=osm&z={z}&x={x}&y={y}&format=png&filter=median,edge
```
