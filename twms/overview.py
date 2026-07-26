# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

import projections
import config

layers = config.layers
wms_name = config.wms_name


def _layer_bounds(layer):
    return layer.get(
        "data_bounding_box",
        layer.get("bounds", projections.projs[layer["proj"]]["bounds"]),
    )


def _layer_extension(layer):
    return layer.get(
        "ext",
        layer.get("mimetype", "image/jpeg").lower().replace("image/", ""),
    ).lower().replace("jpeg", "jpg")


def html(ref):
    """
    Gives overall information about twms server and its layers in HTML format.
    """
    resp = "<!doctype html>"
    resp += "<html><head><title>"
    resp += wms_name
    resp += "</title></head><body><h2>"
    resp += wms_name
    resp += "</h2><table>"
    for i in layers:
        layer = layers[i]
        bbox = _layer_bounds(layer)
        resp += '<tr><td><img src="'
        resp += (
            ref
            + "?layers="
            + i
            + "&amp;bbox=%s,%s,%s,%s" % bbox
            + '&amp;width=200&amp;format=image/png" width="200" /></td><td><h3>'
        )
        if "provider_url" in layer:
            resp += '<a referrerpolicy="no-referrer" href="'
            resp += layer["provider_url"]
            resp += '">'
            resp += layer["name"]
            resp += "</a>"
        else:
            resp += layer["name"]
        resp += (
            "</h3><b>Bounding box:</b> "
            + str(bbox)
            + ' (show on <a href="http://openstreetmap.org/?minlon=%s&amp;minlat=%s&amp;maxlon=%s&amp;maxlat=%s&amp;box=yes">OSM</a>'
            % bbox
            + ")<br />"
        )
        resp += "<b>Projection:</b> " + layer["proj"] + "<br />"
        resp += "<b>WMS half-link:</b> " + ref + "?layers=" + i + "&amp;<br />"
        resp += (
            "<b>Tiles URL:</b> "
            + ref
            + ""
            + i
            + "/!/!/!."
            + _layer_extension(layer)
            + "<br />"
        )
        resp += "</td></tr>"
    resp += "</table></body></html>"
    return resp
