import json
import math
import mimetypes
import urllib.parse
import xml.etree.ElementTree as ET

import twms
import twms.bbox
import twms.config
import twms.projections


def get_wms_url(layer) -> str:
    """TWMS has somewhat like WMS-C emulation for getting tiles directly."""
    ext = mimetypes.guess_extension(layer["mimetype"])
    return f"{twms.config.service_wms_url}/{layer['prefix']}/{{z}}/{{x}}/{{y}}{ext}"


def get_wmts_url(layer) -> str:
    """Generate simpleProfileTile URL.

    <ResourceURL format="image/png" resourceType="simpleProfileTile"
    template="http://tile.openstreetmap.org/{TileMatrix}/{TileCol}/{TileRow}.png"/>
    """
    ext = mimetypes.guess_extension(layer["mimetype"])
    return f"{twms.config.service_wmts_url}/{layer['prefix']}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}{ext}"


def get_tms_url(layer) -> str:
    ext = mimetypes.guess_extension(layer["mimetype"])
    return f"{twms.config.service_wmts_url}/{layer['prefix']}/{{z}}/{{x}}/{{y}}{ext}"


def get_fs_url(layer) -> str:
    ext = mimetypes.guess_extension(layer["mimetype"])
    return f"file://{twms.config.tiles_cache}{layer['prefix']}/{{z}}/{{x}}/{{y}}{ext}"


def maps_html() -> str:
    """Render TMS layers summary."""
    resp = [
        f"""
        <!doctype html><html><head>
        <title>{twms.config.wms_name}</title>
        <style>
        .entry {{
            display: inline-block;
            vertical-align: top;
            width:256px;
            padding: 5px;
        }}
        </style>
        </head><body><h2>{twms.config.wms_name}</h2>
    """
    ]

    for layer_id, layer in twms.config.layers.items():
        proj = layer["proj"]
        # Allowed bounds for a given projection
        bbox = layer.get("bounds", twms.projections.projs[proj]["bounds"])
        resp.append('<div class="entry">')

        if "min_zoom" in layer and layer["min_zoom"] > 8:  # Too recursive
            resp.append("<p>Preview unavailable</p>")
        else:
            resp.append(
                f'<img src="wms?layers={layer_id}&amp;bbox=%s,%s,%s,%s&amp;width=200&amp;format=image/png" width="200" />'
                % bbox
            )

        if "provider_url" in layer:
            resp.append(
                f'<h3><a referrerpolicy="no-referrer" title="Visit tile provider website" href="{layer["provider_url"]}">{layer["name"]}</a></h3>'
            )
        else:
            resp.append(f"<h3>{layer['name']}</h3>")

        resp.append(
            f'<b>Bounding box: </b><a href="{"https://openstreetmap.org/?minlon=%s&amp;minlat=%s&amp;maxlon=%s&amp;maxlat=%s&amp;box=yes" % bbox}">{bbox}</a><br>'
            f"<b>Projection:</b> {proj}<br />"
            f"<b>WMS half-link:</b> {twms.config.service_url}?layers={layer_id}&amp;<br />"
        )
        # Links for JOSM remote control. See https://josm.openstreetmap.de/wiki/Help/RemoteControlCommands#imagery
        josm_link = "http://127.0.0.1:8111/"
        josm_params = {
            "title": layer["name"],
            "type": "tms",
            "valid-georeference": "true",  # Hide annoying warning
        }
        tms_tpl = f'<a title="Import layer with JOSM remote control" href="{josm_link}imagery?{{josm_params}}">tms:</a>{{tms_uri}}<br />'

        josm_params["url"] = get_wms_url(layer)
        resp.append(
            tms_tpl.format(
                josm_params=urllib.parse.urlencode(josm_params),
                tms_uri=josm_params["url"],
            )
        )

        # Faster URI for tiles stored in the same projection
        if proj == "EPSG:3857":
            josm_params["url"] = get_tms_url(layer)
            resp.append(
                tms_tpl.format(
                    josm_params=urllib.parse.urlencode(josm_params),
                    tms_uri=josm_params["url"],
                )
            )

            josm_params["url"] = get_fs_url(layer)
            resp.append(
                tms_tpl.format(
                    josm_params=urllib.parse.urlencode(josm_params),
                    tms_uri=josm_params["url"],
                )
            )
        resp.append("</div>")

    resp.append("</body></html>")
    return "".join(resp)


def maps_xml_josm() -> str:
    """Create XML for JOSM 'imagery.layers.sites' property.

    XML spec https://josm.openstreetmap.de/wiki/Maps
    ELI https://github.com/osmlab/editor-layer-index
    JOSM source https://josm.openstreetmap.de/doc/org/openstreetmap/josm/data/imagery/ImageryLayerInfo.html

        Mandatory tags: <entry>: (<name>, <id>, <type>, <url>)

    XML examples:
        https://josm.openstreetmap.de/maps%<?ids=>  # JOSM URL for fetching
        https://osmlab.github.io/editor-layer-index/imagery.xml
        http://www.imagico.de/map/osmim-imagicode.xml
    """
    # Green color means it already added
    # 1. category - shows as an icon
    # 2. country-code - empty for worldwide
    # 3. name
    # 4. url, but with tms prefox, min-max zoom
    imagery = ET.Element("imagery")
    for layer_id, layer in twms.config.layers.items():
        proj = layer["proj"]
        entry = ET.SubElement(imagery, "entry")
        if "overlay" in layer and layer["overlay"] is True:
            entry.attrib["overlay"] = "true"
        # entry.attrib['eli-best'] = 'true'  # Some JOSM hint/tooltip
        ET.SubElement(
            entry, "default"
        ).text = "true"  # Will be added on first JOSM run?

        ET.SubElement(entry, "name").text = f"twms {layer_id}"  # Must be in English
        ET.SubElement(entry, "id").text = "twms_" + layer_id
        ET.SubElement(entry, "type").text = "tms"
        if proj == "EPSG:3857":
            ET.SubElement(entry, "url").text = get_wmts_url(layer)  # Implement CDATA?
        else:
            # tms_handler not supports reprojection
            ET.SubElement(entry, "url").text = get_wms_url(layer)  # Implement CDATA?
        # Optional tags below
        ET.SubElement(entry, "description").text = layer["name"]  # Must be in English
        if "bounds" in layer:
            ET.SubElement(entry, "bounds").attrib.update(
                {
                    "min-lon": str(layer["bounds"][0]),
                    "min-lat": str(layer["bounds"][1]),
                    "max-lon": str(layer["bounds"][2]),
                    "max-lat": str(layer["bounds"][3]),
                }
            )

        if "dead_tile" in layer:
            no_tile = ET.SubElement(entry, "no-tile-checksum")
            no_tile.attrib["type"] = "MD5"  # Upper case only
            no_tile.attrib["value"] = layer["dead_tile"]["md5"]
        ET.SubElement(
            entry, "valid-georeference"
        ).text = "true"  # Don't annoy with banner

        if "max_zoom" in layer:
            ET.SubElement(entry, "max-zoom").text = str(layer["max_zoom"])

        if "min_zoom" in layer:
            ET.SubElement(entry, "min-zoom").text = str(layer["min_zoom"])
    return ET.tostring(imagery, encoding="unicode")


def maps_xml_wms111() -> str:
    """Minimal WMS GetCapabilities v1.1.1 XML implementation.

    See https://github.com/JOSM/josm/blob/master/src/org/openstreetmap/josm/io/imagery/WMSImagery.java

    1.1.1 vs 1.3.0
        https://docs.qgis.org/3.28/en/docs/server_manual/services/wms.html
        https://docs.geoserver.org/latest/en/user/services/wms/basics.html

    Returns:
        XML "application/vnd.ogc.wms_xml"
    """

    def add_url(parent) -> None:
        """Pass link with path to client."""
        ET.SubElement(
            ET.SubElement(
                ET.SubElement(ET.SubElement(parent, "DCPType"), "HTTP"), "Get"
            ),
            "OnlineResource",
            attrib={
                "{http://www.w3.org/1999/xlink}type": "simple",
                "{http://www.w3.org/1999/xlink}href": twms.config.service_wms_url,
            },
        )

    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    # See 7.2.4 GetCapabilities response
    root = ET.Element(
        "WMT_MS_Capabilities",
        attrib={"version": "1.1.1"},
    )
    service = ET.SubElement(root, "Service")
    # It shall include a Name, Title, and Online Resource URL
    ET.SubElement(service, "Name").text = "OGC:WMS"  # Shall be "OGC:WMS" for v1.1.1
    ET.SubElement(service, "Title").text = twms.config.wms_name
    # This is superseeded by DCPType/HTTP/Get anuway
    ET.SubElement(
        service,
        "OnlineResource",
        attrib={
            "{http://www.w3.org/1999/xlink}type": "simple",
            "{http://www.w3.org/1999/xlink}href": twms.config.service_wms_url,
        },
    )
    capability = ET.SubElement(root, "Capability")
    request = ET.SubElement(capability, "Request")

    get_capabilities = ET.SubElement(request, "GetCapabilities")
    ET.SubElement(get_capabilities, "Format").text = "application/vnd.ogc.wms_xml"
    add_url(get_capabilities)

    get_map = ET.SubElement(request, "GetMap")
    for image_mimetype in ("image/jpeg", "image/png", "image/webp"):
        ET.SubElement(get_map, "Format").text = image_mimetype
    add_url(get_map)

    exceptions = ET.SubElement(capability, "Exception")
    for exc_mimetype in (
        "application/vnd.ogc.se_xml",
        "application/vnd.ogc.se_inimage",
        "application/vnd.ogc.se_blank",
    ):
        ET.SubElement(exceptions, "Format").text = exc_mimetype

    parent_layer = ET.SubElement(capability, "Layer")
    ET.SubElement(parent_layer, "Title").text = twms.config.wms_name

    for proj in sorted(
        twms.projections.projs.keys() | twms.projections.proj_alias.keys()
    ):
        ET.SubElement(parent_layer, "SRS").text = proj

    for layer_id, layer_item in twms.config.layers.items():
        layer = ET.SubElement(parent_layer, "Layer")
        ET.SubElement(layer, "Title").text = layer_item["name"]
        ET.SubElement(layer, "Name").text = layer_id
        # Only "named layers" shall be requested by a client
        # ET.SubElement(layer, "SRS").text = layer_item["proj"]
        bbox = tuple(map(str, layer_item["bounds"]))
        ET.SubElement(
            layer,
            "LatLonBoundingBox",  # EPSG: 4326
            attrib={
                "minx": bbox[0],
                "miny": bbox[1],
                "maxx": bbox[2],
                "maxy": bbox[3],
            },
        )
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def tilejson_document(layer_list: str) -> dict:
    """Build TileJSON metadata for one or more configured layers."""
    layer_ids = [layer_id for layer_id in layer_list.split(",") if layer_id]
    if not layer_ids:
        layer_ids = [
            layer_id
            for layer_id in twms.config.default_layers.split(",")
            if layer_id
        ]
    if not layer_ids:
        raise KeyError("TileJSON requires at least one layer")
    if any(layer_id not in twms.config.layers for layer_id in layer_ids):
        raise KeyError("Unknown layer in TileJSON request")

    layers = [twms.config.layers[layer_id] for layer_id in layer_ids]
    bounds = layers[0]["bounds"]
    for layer in layers[1:]:
        bounds = twms.bbox.add(bounds, layer["bounds"])

    extension = mimetypes.guess_extension(layers[0]["mimetype"]) or ".jpg"
    if extension == ".jpe":
        extension = ".jpg"
    names = urllib.parse.quote(",".join(layer_ids), safe=",")
    min_zoom = max(layer["min_zoom"] for layer in layers)
    max_zoom = min(layer["max_zoom"] for layer in layers)
    return {
        "tilejson": "3.0.0",
        "name": ", ".join(layer["name"] for layer in layers),
        "scheme": "xyz",
        "tiles": [
            f"{twms.config.service_wms_url}/{names}/{{z}}/{{x}}/{{y}}{extension}"
        ],
        "bounds": list(bounds),
        "center": [
            (bounds[0] + bounds[2]) / 2,
            (bounds[1] + bounds[3]) / 2,
            min_zoom,
        ],
        "minzoom": min_zoom,
        "maxzoom": max_zoom,
    }


def tilejson_json(layer_list: str) -> str:
    return json.dumps(tilejson_document(layer_list), sort_keys=True)


def maps_xml_wms130() -> str:
    """Minimal WMS GetCapabilities v1.3.0 XML implementation.

    WMS 1.3.0 GetCapabilities response.

    WMS_Capabilities
        Service
            Name
            OnlineResource
        Capability
            Request
            Exception
            Layer

    Returns:
        XML
    """
    ET.register_namespace("", "http://www.opengis.net/wms")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    # See 7.2.4 GetCapabilities response
    root = ET.Element(
        "{http://www.opengis.net/wms}WMS_Capabilities",
        attrib={"version": "1.3.0"},
    )
    service = ET.SubElement(root, "Service")
    # It shall include a Name, Title, and Online Resource URL
    ET.SubElement(service, "Name").text = "WMS"  # Shall always be "WMS"
    ET.SubElement(service, "Title").text = twms.config.wms_name
    # This is superseeded by DCPType/HTTP/Get anuway
    ET.SubElement(
        service,
        "OnlineResource",
        attrib={"{http://www.w3.org/1999/xlink}href": twms.config.service_wms_url},
    )
    capability = ET.SubElement(root, "Capability")
    request = ET.SubElement(capability, "Request")
    get_capabilities = ET.SubElement(request, "GetCapabilities")
    ET.SubElement(get_capabilities, "Format").text = "text/xml"
    ET.SubElement(
        ET.SubElement(ET.SubElement(ET.SubElement(get_capabilities, "DCPType"), "HTTP"), "Get"),
        "OnlineResource",
        attrib={"{http://www.w3.org/1999/xlink}href": twms.config.service_wms_url},
    )

    getmap = ET.SubElement(request, "GetMap")
    for image_mimetype in ("image/jpeg", "image/png", "image/webp"):
        ET.SubElement(getmap, "Format").text = image_mimetype
    # Way to pass link with path to client
    ET.SubElement(
        ET.SubElement(ET.SubElement(ET.SubElement(getmap, "DCPType"), "HTTP"), "Get"),
        "OnlineResource",
        attrib={"{http://www.w3.org/1999/xlink}href": twms.config.service_wms_url},
    )

    exceptions = ET.SubElement(capability, "Exception")
    ET.SubElement(exceptions, "Format").text = "XML"
    root_layer = ET.SubElement(capability, "Layer")
    ET.SubElement(root_layer, "Title").text = twms.config.wms_name
    ET.SubElement(root_layer, "CRS").text = "CRS:84"
    for layer_id, layer_item in twms.config.layers.items():
        layer = ET.SubElement(root_layer, "Layer")
        ET.SubElement(layer, "Title").text = layer_item["name"]
        ET.SubElement(layer, "Name").text = layer_id

        bbox = tuple(map(str, layer_item["bounds"]))
        geo_bbox = ET.SubElement(layer, "EX_GeographicBoundingBox")
        ET.SubElement(geo_bbox, "westBoundLongitude").text = bbox[0]
        ET.SubElement(geo_bbox, "eastBoundLongitude").text = bbox[2]
        ET.SubElement(geo_bbox, "southBoundLatitude").text = bbox[1]
        ET.SubElement(geo_bbox, "northBoundLatitude").text = bbox[3]
        ET.SubElement(layer, "CRS").text = "CRS:84"
        ET.SubElement(
            layer,
            "BoundingBox",
            attrib={
                "CRS": "CRS:84",
                "minx": bbox[0],
                "miny": bbox[1],
                "maxx": bbox[2],
                "maxy": bbox[3],
            },
        )
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


class TileMatrixSet:
    """Generate OSC TileMatrixSet for WMTS.

    https://github.com/mapproxy/mapproxy/blob/master/mapproxy/service/wmts.py#LL356C4-L356C4
    https://github.com/mapproxy/mapproxy/blob/d6834781bb81bcfb2ba36ed7f8430633c54b4cf6/mapproxy/grid.py#L1070
    """

    tmsets = {
        # Mapproxy GLOBAL_GEODETIC
        # https://paituli.csc.fi/geoserver/ogc/tiles/tileMatrixSets/WorldCRS84Quad
        "urn:ogc:def:crs:OGC:1.3:CRS84": {  # Shall be "WorldCRS84Quad" or "InspireCRS84Quad" by Simple spec
            "Identifier": "WorldCRS84Quad",  # From Simple spec
            "WellKnownScaleSet": "urn:ogc:def:wkss:OGC:1.0:GoogleCRS84Quad",  # Pixel size 1.40625000000000
            "topLeftCorner": "-180.0 90.0",  # Exactly this. Extent fits on a 512x256 image
            "resourceType": "simpleProfileCSR84Tile",
        },
        # Spherical Mercator (WGS 84/Pseudo-Mercator): Google, OpenStreetMap, VirtualEarth
        # Mapproxy GLOBAL_WEBMERCATOR
        # https://paituli.csc.fi/geoserver/ogc/tiles/tileMatrixSets/EPSG%3A3857
        "urn:ogc:def:crs:EPSG::3857": {
            "Identifier": "WorldWebMercatorQuad",  # From Simple spec
            # Dot typo ("urn:ogc:def:crs:EPSG:6.18.3:3857") in some services, here as given in spec and OpenLayers
            # "crs": "urn:ogc:def:crs:EPSG:6.18:3:3857",  # Note valid ':'
            "WellKnownScaleSet": "urn:ogc:def:wkss:OGC:1.0:GoogleMapsCompatible",  # Pixel size 156543.0339280410
            "topLeftCorner": "-20037508.3427892 20037508.3427892",  # Exactly this. Extent fits on a 256x256 image
            "resourceType": "simpleProfileTile",
        },
        # Ellipsoid Mercator (WGS 84 compliant) WGS 84/World Mercator на сфероиде. Космоснимки, Яндекс.Карты
        # https://paituli.csc.fi/geoserver/ogc/tiles/tileMatrixSets/WorldMercatorWGS84Quad
        "http://www.opengis.net/def/crs/EPSG/0/3395": {
            "Identifier": "WorldMercatorWGS84Quad",
            "WellKnownScaleSet": "http://www.opengis.net/def/wkss/OGC/1.0/WorldMercatorWGS84",
            "TopLeftCorner": "-20037508.3427892 20037508.3427892",
            "resourceType": "tile",
        },
    }

    def __init__(self):
        """Calculate "GoogleMapsCompatible" tile grid scale denominator for z0 level.

        Earth sphere circumference (2*pi*r) taken to determine top tile resolution.

        >>> import math
        >>> 2 * math.pi * 6378137 / 256 / (0.28 / 1000)
        559082264.0287176
        >>> 40075016.68557849 / 256 / (0.28 / 1000)  # z0 ScaleDenominator
        559082264.0287176
        """
        self.sradiusa = 6378137  # WGS84 spheroid radius
        # Non-square pixels aren't supporteed by the spec
        # sradiusb = 6356752.314  # WGS84 ellipsoid radius
        self.tile_size = 256
        self.ogc_pixel_size = 0.28 / 1000  # m/px
        self.earth_circumference = 2 * math.pi * self.sradiusa  # meters
        assert self.earth_circumference == 40075016.68557849

        # Compatible with "urn:ogc:def:wkss:OGC:1.0:GoogleMapsCompatible" MatrixSet
        self.mercator_crs = (
            twms.projections.EPSG("EPSG:3395"),
            twms.projections.EPSG("EPSG:3857"),
        )

    def add_xml_element(
        self, parent: ET.Element, proj: twms.projections.EPSG, levels: int = 24
    ) -> None:
        """Append TileMatrixSet to Capabilities XML.

        Cannot declare multiple TileMatrixSets with same Identifier
        (i.e. Simple WMTS "WorldCRS84Quad", "WorldWebMercatorQuad")
        but different CRS.
        """
        wkss = None
        if proj in self.mercator_crs:
            # km 40075.017, 40075016.6856
            top_left = "-20037508.3427892 20037508.3427892"  # From WMTS Simple spec
            # top_left = "-20037508.342789244 20037508.342789244"
            # assert self.pixel_resolution == 156543.03392804097 # meter per equatorial px
            # assert self.scale_denom == 559082264.0287176
            wkss = "urn:ogc:def:wkss:OGC:1.0:GoogleMapsCompatible"
        else:
            top_left = "-180.0 90.0"
        pixel_resolution = self.earth_circumference / self.tile_size
        scale_denominator = pixel_resolution / self.ogc_pixel_size  # Always meters

        # Annex E provides several well-known scale sets for TileMatrixSetDef
        # Mandatory: Identifier (ows:CodeType), SupportedCRS (URI), tileMatrix
        # Optional wellKnownScaleSet
        tilematrixset = ET.SubElement(parent, "TileMatrixSet")
        ET.SubElement(
            tilematrixset, "{http://www.opengis.net/ows/1.1}Identifier"
        ).text = proj

        # JOSM looks for "urn:ogc:def:crs:" with "urn:ogc:def:crs:([^:]*)(?::.*)?:(.*)$",
        # so double semicolon like "urn:ogc:def:crs:EPSG::3857" should be fine
        # https://josm.openstreetmap.de/browser/josm/trunk/src/org/openstreetmap/josm/data/imagery/GetCapabilitiesParseHelper.java
        ET.SubElement(
            tilematrixset, "{http://www.opengis.net/ows/1.1}SupportedCRS"
        ).text = ("urn:ogc:def:crs:EPSG::" + proj.rsplit(":")[-1])
        # A WKSS is a commonly used combination of a CRS and a set of scales
        # https://docs.ogc.org/is/17-083r2/17-083r2.html
        if proj == "EPSG:3857":
            ET.SubElement(tilematrixset, "WellKnownScaleSet").text = wkss

        scale_factor = 2
        # Mandatory: Identifier, ScaleDenominator, TopLeftCorner, TileWidth, TileHeight, MatrixWidth, MatrixHeight
        # Recommended (but not mandatory) "Identifier" specified in Simple profile
        for level in range(levels):
            tilematrix = ET.SubElement(tilematrixset, "TileMatrix")
            matrix_width = scale_factor**level
            ET.SubElement(
                tilematrix, "{http://www.opengis.net/ows/1.1}Identifier"
            ).text = str(level)
            ET.SubElement(tilematrix, "ScaleDenominator").text = str(
                scale_denominator / matrix_width
            )
            # Half of the Earth circumference (math.pi * sradiusa)
            ET.SubElement(tilematrix, "TopLeftCorner").text = top_left
            ET.SubElement(tilematrix, "TileWidth").text = str(self.tile_size)
            ET.SubElement(tilematrix, "TileHeight").text = str(self.tile_size)
            ET.SubElement(tilematrix, "MatrixWidth").text = str(matrix_width)
            ET.SubElement(tilematrix, "MatrixHeight").text = str(matrix_width)


def maps_wmts_rest() -> str:
    """Open Geospatial Consortium WMTS 1.0.0 implementation.

    Implementation close to OGC WMTS Simple Profile https://docs.ogc.org/is/13-082r2/13-082r2.html

    Returns:
        XML
    """
    ET.register_namespace("", "http://www.opengis.net/wmts/1.0")
    ET.register_namespace("ows", "http://www.opengis.net/ows/1.1")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    # 7.1.1.3 ServiceMetadata document example
    root = ET.Element(
        "{http://www.opengis.net/wmts/1.0}Capabilities",
        attrib={
            "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation": "http://www.opengis.net/wmts/1.0 http://schemas.opengis.net/wmts/1.0/wmtsGetCapabilities_response.xsd",
            "version": "1.0.0",
        },
    )
    service_identification = ET.SubElement(
        root, "{http://www.opengis.net/ows/1.1}ServiceIdentification"
    )
    ET.SubElement(
        service_identification, "{http://www.opengis.net/ows/1.1}Title"
    ).text = twms.config.wms_name
    ET.SubElement(
        service_identification, "{http://www.opengis.net/ows/1.1}ServiceType"
    ).text = "OGC WMTS"
    ET.SubElement(
        service_identification, "{http://www.opengis.net/ows/1.1}ServiceTypeVersion"
    ).text = "1.0.0"

    contents = ET.SubElement(root, "Contents")

    proj_set = set()
    for layer_id, layer_item in twms.config.layers.items():
        # if layer_item["proj"] not in self.tile_matrix_sets:
        #     logging.warning(f"Unsupported projection for '{layer_id}'")
        #     continue
        layer = ET.SubElement(contents, "Layer")
        ET.SubElement(layer, "{http://www.opengis.net/ows/1.1}Title").text = layer_item[
            "name"
        ]
        wgs84_bbox = ET.SubElement(
            layer, "{http://www.opengis.net/ows/1.1}WGS84BoundingBox"
        )
        ET.SubElement(
            wgs84_bbox, "{http://www.opengis.net/ows/1.1}LowerCorner"
        ).text = "{} {}".format(*layer_item["bounds"])
        ET.SubElement(
            wgs84_bbox, "{http://www.opengis.net/ows/1.1}UpperCorner"
        ).text = "{2} {3}".format(*layer_item["bounds"])
        ET.SubElement(
            layer, "{http://www.opengis.net/ows/1.1}Identifier"
        ).text = layer_id
        # Style mandatory: Identifier,
        style = ET.SubElement(layer, "Style", attrib={"isDefault": "true"})
        ET.SubElement(
            style, "{http://www.opengis.net/ows/1.1}Identifier"
        ).text = "default"
        ET.SubElement(layer, "Format").text = layer_item["mimetype"]

        tilematrixset_link = ET.SubElement(layer, "TileMatrixSetLink")
        ET.SubElement(tilematrixset_link, "TileMatrixSet").text = layer_item["proj"]
        # resourceType: ("tile", "simpleProfileTile", "simpleProfileCRSTile").
        # JOSM supports "tile" only
        ET.SubElement(
            layer,
            "ResourceURL",
            attrib={
                "format": layer_item["mimetype"],
                "resourceType": "tile",
                "template": get_wmts_url(layer_item),
            },
        )
        proj_set.add(layer_item["proj"])

    tm_set = TileMatrixSet()
    for proj in proj_set:
        tm_set.add_xml_element(contents, proj=proj)
    # tm_set.add_xml_element(contents, proj="CRS84")

    ET.SubElement(
        root,
        "ServiceMetadataURL",
        attrib={
            "{http://www.w3.org/1999/xlink}href": f"{twms.config.service_wmts_url}/1.0.0/WMTSCapabilities.xml"
        },
    )
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
