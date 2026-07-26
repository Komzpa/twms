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


def document(config, ref):
    root = ET.Element(_tag("imagery"))
    for layer_name in sorted(config.layers):
        layer = config.layers[layer_name]
        entry = ET.SubElement(root, _tag("entry"))
        ET.SubElement(entry, _tag("name")).text = layer.get("name", layer_name)
        ET.SubElement(entry, _tag("id")).text = "twms-%s" % layer_name
        ET.SubElement(entry, _tag("type")).text = "tms"
        ET.SubElement(entry, _tag("url")).text = _layer_url(ref, layer_name, layer)
        if "provider_url" in layer:
            ET.SubElement(entry, _tag("attribution-url")).text = layer["provider_url"]
        if "max_zoom" in layer:
            ET.SubElement(entry, _tag("max-zoom")).text = str(layer["max_zoom"] - 1)
        if "min_zoom" in layer:
            ET.SubElement(entry, _tag("min-zoom")).text = str(layer["min_zoom"])
    return root


def xml(config, ref):
    return ET.tostring(document(config, ref), encoding="unicode", xml_declaration=True)
