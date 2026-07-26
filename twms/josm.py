# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

import xml.etree.ElementTree as ET


JOSM_MAPS = "http://josm.openstreetmap.de/maps-1.0"
ET.register_namespace("", JOSM_MAPS)


def _tag(name):
    return "{%s}%s" % (JOSM_MAPS, name)


def _layer_extension(layer):
    return layer.get("ext", "jpg").lower().replace("jpeg", "jpg")


def _layer_url(ref, layer_name, layer):
    return "%s%s/{zoom}/{x}/{y}.%s" % (
        ref,
        layer_name,
        _layer_extension(layer),
    )


def _layer_bounds(config, layer):
    return layer.get(
        "data_bounding_box",
        layer.get("bounds", layer.get("bbox", config.default_bbox)),
    )


def _dead_tile_md5_values(layer):
    dead_tile = layer.get("dead_tile")
    if not isinstance(dead_tile, dict) or "md5" not in dead_tile:
        return ()
    md5 = dead_tile["md5"]
    if isinstance(md5, str):
        return (md5,)
    try:
        return tuple(sorted(md5))
    except TypeError:
        return ()


def document(config, ref):
    root = ET.Element(_tag("imagery"))
    for layer_name in sorted(config.layers):
        layer = config.layers[layer_name]
        attrs = {}
        if layer.get("overlay"):
            attrs["overlay"] = "true"
        entry = ET.SubElement(root, _tag("entry"), attrs)
        ET.SubElement(entry, _tag("default")).text = "true"
        ET.SubElement(entry, _tag("name")).text = layer.get("name", layer_name)
        ET.SubElement(entry, _tag("id")).text = "twms-%s" % layer_name
        ET.SubElement(entry, _tag("type")).text = "tms"
        ET.SubElement(entry, _tag("url")).text = _layer_url(ref, layer_name, layer)
        ET.SubElement(entry, _tag("description")).text = layer.get("name", layer_name)
        bounds = _layer_bounds(config, layer)
        ET.SubElement(
            entry,
            _tag("bounds"),
            {
                "min-lon": str(bounds[0]),
                "min-lat": str(bounds[1]),
                "max-lon": str(bounds[2]),
                "max-lat": str(bounds[3]),
            },
        )
        ET.SubElement(entry, _tag("valid-georeference")).text = "true"
        if "provider_url" in layer:
            ET.SubElement(entry, _tag("attribution-url")).text = layer["provider_url"]
        for md5 in _dead_tile_md5_values(layer):
            ET.SubElement(
                entry,
                _tag("no-tile-checksum"),
                {
                    "type": "MD5",
                    "value": md5,
                },
            )
        if "max_zoom" in layer:
            ET.SubElement(entry, _tag("max-zoom")).text = str(layer["max_zoom"] - 1)
        if "min_zoom" in layer:
            ET.SubElement(entry, _tag("min-zoom")).text = str(layer["min_zoom"])
    return root


def xml(config, ref):
    return ET.tostring(document(config, ref), encoding="unicode", xml_declaration=True)
