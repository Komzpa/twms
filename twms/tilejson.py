# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

import json

import bbox


def _layer_names(config, layers):
    names = [name for name in layers.split(",") if name]
    if not names:
        names = [name for name in config.default_layers.split(",") if name]
    if not names:
        raise KeyError("TileJSON needs an existing layer name")
    for name in names:
        if name not in config.layers:
            raise KeyError("Unknown layer: %s" % name)
    return names


def _layer_bounds(config, layer):
    return layer.get(
        "data_bounding_box",
        layer.get("bounds", layer.get("bbox", config.default_bbox)),
    )


def _tile_extension(config, layer_names, format_name):
    if format_name:
        return format_name.lower().replace("image/", "").replace("jpeg", "jpg")
    if len(layer_names) == 1:
        return config.layers[layer_names[0]].get("ext", "jpg")
    return config.default_format.lower().replace("image/", "").replace("jpeg", "jpg")


def document(config, layers, ref, format_name=""):
    layer_names = _layer_names(config, layers)
    layer_items = [config.layers[name] for name in layer_names]
    bounds = _layer_bounds(config, layer_items[0])
    for layer in layer_items[1:]:
        bounds = bbox.add(bounds, _layer_bounds(config, layer))

    minzoom = max(layer.get("min_zoom", 0) for layer in layer_items)
    maxzoom = min(layer.get("max_zoom", config.default_max_zoom) for layer in layer_items)
    center = [
        (bounds[0] + bounds[2]) / 2.0,
        (bounds[1] + bounds[3]) / 2.0,
        minzoom,
    ]
    ext = _tile_extension(config, layer_names, format_name)
    tile_url = "%s%s/{z}/{x}/{y}.%s" % (ref, ",".join(layer_names), ext)

    return {
        "tilejson": "3.0.0",
        "name": ", ".join(layer["name"] for layer in layer_items),
        "scheme": "xyz",
        "tiles": [tile_url],
        "bounds": list(bounds),
        "center": center,
        "minzoom": minzoom,
        "maxzoom": maxzoom,
    }


def dumps(config, layers, ref, format_name=""):
    return json.dumps(
        document(config, layers, ref, format_name=format_name),
        sort_keys=True,
    )
