# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

import xml.etree.ElementTree as ET

import projections


WMTS = "http://www.opengis.net/wmts/1.0"
OWS = "http://www.opengis.net/ows/1.1"
XLINK = "http://www.w3.org/1999/xlink"
XSI = "http://www.w3.org/2001/XMLSchema-instance"


def _tag(namespace, name):
    return "{%s}%s" % (namespace, name)


def _extension(layer):
    return layer.get("ext", "jpg").lower().replace("jpeg", "jpg")


def _mime_type(layer):
    ext = _extension(layer)
    if ext == "jpg":
        return "image/jpeg"
    return "image/%s" % ext


def _layer_bounds(config, layer):
    return layer.get(
        "data_bounding_box",
        layer.get("bbox", config.default_bbox),
    )


def _tile_url(ref, layer_name, layer):
    return "%swmts/%s/{TileMatrix}/{TileCol}/{TileRow}.%s" % (
        ref,
        layer_name,
        _extension(layer),
    )


def _supported_crs(proj):
    epsg = proj.split(":")[-1]
    if epsg.isdigit():
        return "urn:ogc:def:crs:EPSG::%s" % epsg
    return proj


def _projected_bounds(proj):
    bounds = projections.projs[projections.proj_alias.get(proj, proj)]["bounds"]
    return projections.from4326(bounds, proj)


def _scale_denominator(proj, z):
    projected = _projected_bounds(proj)
    matrix_width = 2 ** z
    resolution = (projected[2] - projected[0]) / (256 * matrix_width)
    return resolution / 0.00028


def _max_zoom_for_proj(config, proj):
    zooms = [
        layer.get("max_zoom", config.default_max_zoom)
        for layer in config.layers.values()
        if layer.get("proj", "EPSG:3857") == proj
    ]
    return max(zooms or [config.default_max_zoom])


def _add_operation(parent, name, href):
    operation = ET.SubElement(parent, _tag(OWS, "Operation"), {"name": name})
    dcp = ET.SubElement(operation, _tag(OWS, "DCP"))
    http = ET.SubElement(dcp, _tag(OWS, "HTTP"))
    ET.SubElement(
        http,
        _tag(OWS, "Get"),
        {_tag(XLINK, "href"): href},
    )


def _add_layer(parent, config, layer_name, layer, ref):
    layer_element = ET.SubElement(parent, _tag(WMTS, "Layer"))
    ET.SubElement(layer_element, _tag(OWS, "Title")).text = layer["name"]
    ET.SubElement(layer_element, _tag(OWS, "Identifier")).text = layer_name

    wgs84_bounds = ET.SubElement(layer_element, _tag(OWS, "WGS84BoundingBox"))
    bounds = _layer_bounds(config, layer)
    ET.SubElement(wgs84_bounds, _tag(OWS, "LowerCorner")).text = "%s %s" % (
        bounds[0],
        bounds[1],
    )
    ET.SubElement(wgs84_bounds, _tag(OWS, "UpperCorner")).text = "%s %s" % (
        bounds[2],
        bounds[3],
    )

    style = ET.SubElement(layer_element, _tag(WMTS, "Style"), {"isDefault": "true"})
    ET.SubElement(style, _tag(OWS, "Identifier")).text = "default"
    ET.SubElement(layer_element, _tag(WMTS, "Format")).text = _mime_type(layer)

    link = ET.SubElement(layer_element, _tag(WMTS, "TileMatrixSetLink"))
    ET.SubElement(link, _tag(WMTS, "TileMatrixSet")).text = layer.get("proj", "EPSG:3857")
    ET.SubElement(
        layer_element,
        _tag(WMTS, "ResourceURL"),
        {
            "format": _mime_type(layer),
            "resourceType": "tile",
            "template": _tile_url(ref, layer_name, layer),
        },
    )


def _add_tile_matrix_set(parent, config, proj):
    projected = _projected_bounds(proj)
    tile_matrix_set = ET.SubElement(parent, _tag(WMTS, "TileMatrixSet"))
    ET.SubElement(tile_matrix_set, _tag(OWS, "Identifier")).text = proj
    ET.SubElement(tile_matrix_set, _tag(OWS, "SupportedCRS")).text = _supported_crs(proj)

    for z in range(_max_zoom_for_proj(config, proj) + 1):
        matrix_size = 2 ** z
        tile_matrix = ET.SubElement(tile_matrix_set, _tag(WMTS, "TileMatrix"))
        ET.SubElement(tile_matrix, _tag(OWS, "Identifier")).text = str(z)
        ET.SubElement(tile_matrix, _tag(WMTS, "ScaleDenominator")).text = str(
            _scale_denominator(proj, z)
        )
        ET.SubElement(tile_matrix, _tag(WMTS, "TopLeftCorner")).text = "%s %s" % (
            projected[0],
            projected[3],
        )
        ET.SubElement(tile_matrix, _tag(WMTS, "TileWidth")).text = "256"
        ET.SubElement(tile_matrix, _tag(WMTS, "TileHeight")).text = "256"
        ET.SubElement(tile_matrix, _tag(WMTS, "MatrixWidth")).text = str(matrix_size)
        ET.SubElement(tile_matrix, _tag(WMTS, "MatrixHeight")).text = str(matrix_size)


def capabilities(config, ref):
    ET.register_namespace("", WMTS)
    ET.register_namespace("ows", OWS)
    ET.register_namespace("xlink", XLINK)
    ET.register_namespace("xsi", XSI)

    root = ET.Element(
        _tag(WMTS, "Capabilities"),
        {
            "version": "1.0.0",
            _tag(XSI, "schemaLocation"): (
                "http://www.opengis.net/wmts/1.0 "
                "http://schemas.opengis.net/wmts/1.0/wmtsGetCapabilities_response.xsd"
            ),
        },
    )
    service = ET.SubElement(root, _tag(OWS, "ServiceIdentification"))
    ET.SubElement(service, _tag(OWS, "Title")).text = config.wms_name
    ET.SubElement(service, _tag(OWS, "ServiceType")).text = "OGC WMTS"
    ET.SubElement(service, _tag(OWS, "ServiceTypeVersion")).text = "1.0.0"

    operations = ET.SubElement(root, _tag(OWS, "OperationsMetadata"))
    _add_operation(
        operations,
        "GetCapabilities",
        "%swmts/1.0.0/WMTSCapabilities.xml" % ref,
    )
    _add_operation(operations, "GetTile", ref)

    contents = ET.SubElement(root, _tag(WMTS, "Contents"))
    projections_in_use = set()
    for layer_name in sorted(config.layers.keys()):
        layer = config.layers[layer_name]
        proj = layer.get("proj", "EPSG:3857")
        if proj not in projections.projs:
            continue
        projections_in_use.add(proj)
        _add_layer(contents, config, layer_name, layer, ref)

    for proj in sorted(projections_in_use):
        _add_tile_matrix_set(contents, config, proj)

    ET.SubElement(
        root,
        _tag(WMTS, "ServiceMetadataURL"),
        {_tag(XLINK, "href"): "%swmts/1.0.0/WMTSCapabilities.xml" % ref},
    )

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root,
        encoding="unicode",
    )
