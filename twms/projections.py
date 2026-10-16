import collections.abc
import math
from typing import NewType

import twms.bbox
import twms.config

EPSG = NewType("EPSG", str)  # Like pyproj.CRS

projs: dict[str, dict[str, str | twms.bbox.Bbox]] = {
    "EPSG:4326": {
        "proj": "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs",
        "bounds": (-180.0, -90.0, 180.0, 90.0),
    },
    "NASA:4326": {
        "proj": "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs",
        "bounds": (-180.0, -166.0, 332.0, 346.0),
    },
    "EPSG:3395": {
        "proj": "+proj=merc +lon_0=0 +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        "bounds": (-180.0, -85.0840591556, 180.0, 85.0840590501),
    },
    "EPSG:3857": {
        "proj": "+proj=merc +lon_0=0 +lat_ts=0 +x_0=0 +y_0=0 +a=6378137 +b=6378137 +units=m +no_defs",
        "bounds": (-180.0, -85.0511287798, 180.0, 85.0511287798),
    },
    "EPSG:32635": {
        "proj": "+proj=utm +zone=35 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        "bounds": (-180.0, -90.0, 180.0, 90.0),
    },
    "EPSG:32636": {
        "proj": "+proj=utm +zone=36 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        "bounds": (-180.0, -90.0, 180.0, 90.0),
    },
    "EPSG:32637": {
        "proj": "+proj=utm +zone=37 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        "bounds": (-180.0, -90.0, 180.0, 90.0),
    },
    "EPSG:32638": {
        "proj": "+proj=utm +zone=38 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        "bounds": (-180.0, -90.0, 180.0, 90.0),
    },
    "EPSG:32639": {
        "proj": "+proj=utm +zone=39 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        "bounds": (-180.0, -90.0, 180.0, 90.0),
    },
    "EPSG:32640": {
        "proj": "+proj=utm +zone=40 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        "bounds": (-180.0, -90.0, 180.0, 90.0),
    },
    "EPSG:32641": {
        "proj": "+proj=utm +zone=41 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        "bounds": (-180.0, -90.0, 180.0, 90.0),
    },
    "EPSG:32642": {
        "proj": "+proj=utm +zone=42 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        "bounds": (-180.0, -90.0, 180.0, 90.0),
    },
}


proj_alias = {
    EPSG("EPSG:900913"): EPSG("EPSG:3857"),
    EPSG("EPSG:3785"): EPSG("EPSG:3857"),
    EPSG("CRS:84"): EPSG("EPSG:4326"),
}


def _c4326t3857(t1, t2, lon: float, lat: float) -> twms.bbox.Point:
    """Pure python 4326 -> 3857 transform. About 8x faster than pyproj.

    Args:
        lon: -180...180 degrees
        lat: -85.06...85.06 degrees

    Returns:
        EPSG:3857 bounds must be in range `6378137 * math.pi`.

    >>> _c4326t3857(0, 0, 27.6, 53.2)
    (3072417.9458943508, 7020078.532642099)

    >>> _c4326t3857(0, 0, -180, 85)
    (-20037508.342789244, 19971868.880408566)

    >>> _c4326t3857(0, 0, -180, -90.0)
    (-20037508.342789244, -20037508.342789244)

    >>> _c4326t3857(0, 0, 180, 90.0)
    (20037508.342789244, 20037508.342789244)
    """
    maxbounds = 6378137 * math.pi
    xtile = maxbounds / 180 * lon
    lat_rad = math.radians(lat)
    # Limit lat, otherwise log(0) will cause exception
    if abs(lat) <= 85.0511287798:
        ytile = (
            math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi * maxbounds
        )
    else:
        ytile = math.copysign(maxbounds, lat)
    return xtile, ytile


def _c3857t4326(t1, t2, lon: float, lat: float) -> twms.bbox.Point:
    """Pure python 3857 -> 4326 transform. About 12x faster than pyproj.

    >>> point = _c4326t3857(1, 2, 27.6, 53.2)
    >>> _c3857t4326(1, 2, point[0], point[1])
    (27.599999999999998, 53.20000000000001)
    """
    xtile = lon / 111319.49079327358
    ytile = math.degrees(math.asin(math.tanh(lat / 20037508.342789244 * math.pi)))
    return xtile, ytile


def _c4326t3395(t1, t2, lon: float, lat: float) -> twms.bbox.Point:
    """Pure python 4326 -> 3395 transform. About 8x faster than pyproj.

    >>> _c4326t3395(1, 2, 27.6, 53.2)
    (3072417.9458943508, 6985840.123947986)
    """
    E = 0.0818191908426
    # A = 20037508.342789
    # F = 53.5865938
    tmp = math.tan(math.pi / 4 + math.radians(lat) / 2.0)
    pow_tmp = math.pow(
        math.tan(math.pi / 4 + math.asin(E * math.sin(math.radians(lat))) / 2.0),
        E,
    )
    x = lon * 111319.49079327358
    y = 6378137.0 * math.log(tmp / pow_tmp)
    return x, y


def _c3395t4326(t1, t2, lon: float, lat: float) -> twms.bbox.Point:
    """Pure python 4326 -> 3395 transform. About 3x faster than pyproj.

    Typically used for Yandex tiles reprojection to Slippy map.

    >>> point = _c4326t3395(1, 2, 27.6, 53.2)
    >>> _c3395t4326(1, 2, point[0], point[1])
    (27.599999999999998, 53.19999999779212)
    """
    r_major = 6378137.000
    temp = 6356752.3142 / 6378137.000
    es = 1.0 - (temp * temp)
    eccent = math.sqrt(es)
    ts = math.exp(-lat / r_major)
    HALFPI = math.pi / 2
    eccnth = 0.5 * eccent
    Phi = HALFPI - 2.0 * math.atan(ts)
    N_ITER = 15
    TOL = 1e-7
    i = N_ITER
    dphi = 0.1
    while abs(dphi) > TOL and i > 0:
        i -= 1
        con = eccent * math.sin(Phi)
        dphi = (
            HALFPI
            - 2.0 * math.atan(ts * math.pow((1.0 - con) / (1.0 + con), eccnth))
            - Phi
        )
        Phi += dphi

    x = lon / 111319.49079327358
    return x, math.degrees(Phi)


pure_python_transformers = {
    (EPSG("EPSG:4326"), EPSG("EPSG:3857")): _c4326t3857,
    (EPSG("EPSG:3857"), EPSG("EPSG:4326")): _c3857t4326,
    (EPSG("EPSG:4326"), EPSG("EPSG:3395")): _c4326t3395,
    (EPSG("EPSG:3395"), EPSG("EPSG:4326")): _c3395t4326,
}


def tile_by_bbox(bbox: twms.bbox.Bbox, zoom: int, srs: EPSG = EPSG("EPSG:3857")):
    """Convert bbox from EPSG:4326 format to tile numbers of given zoom level, with correct wraping around 180th meridian."""
    a1, a2 = tile_by_coords((bbox[0], bbox[1]), zoom, srs)
    b1, b2 = tile_by_coords((bbox[2], bbox[3]), zoom, srs)
    if b1 < a1:
        b1 += 2 ** (zoom - 1)
    return a1, a2, b1, b2


def bbox_by_tile(
    z: int, x: int, y: int, srs: EPSG = EPSG("EPSG:3857")
) -> twms.bbox.Bbox:
    """Convert tile number to EPSG:4326 bbox of srs-projected tile."""
    a1, a2 = coords_by_tile(z, x, y, srs)
    b1, b2 = coords_by_tile(z, x + 1, y + 1, srs)
    return a1, b2, b1, a2


def zoom_for_bbox(
    bbox: twms.bbox.Bbox,
    size: tuple[int, int],
    layer_id: str,
    min_zoom: int = 1,
    max_zoom: int = 18,
    max_size: tuple[int, int] = (10000, 10000),
) -> int:
    """Calculate a best-fit zoom level."""
    h, w = size
    for i in range(min_zoom, max_zoom):
        cx1, cy1, cx2, cy2 = tile_by_bbox(bbox, i, twms.config.layers[layer_id]["proj"])
        if w != 0:
            if (cx2 - cx1) * 256 >= w * 0.9:
                return i
        if h != 0:
            if (cy1 - cy2) * 256 >= h * 0.9:
                return i
        if (cy1 - cy2) * 256 >= max_size[0] / 2:
            return i
        if (cx2 - cx1) * 256 >= max_size[1] / 2:
            return i
    return max_zoom


def coords_by_tile(
    z: int, x: int, y: int, srs: EPSG = EPSG("EPSG:3857")
) -> twms.bbox.Point:
    """Convert (z,x,y) to coordinates of corner of srs-projected tile."""
    normalized_tile = x / (2.0**z), 1.0 - (y / (2.0**z))
    projected_bounds = from4326(projs[proj_alias.get(srs, srs)]["bounds"], srs)
    maxp = [
        projected_bounds[2] - projected_bounds[0],
        projected_bounds[3] - projected_bounds[1],
    ]
    projected_coords = [
        (normalized_tile[0] * maxp[0]) + projected_bounds[0],
        (normalized_tile[1] * maxp[1]) + projected_bounds[1],
    ]
    return to4326(projected_coords, srs)


def tile_by_coords(xxx_todo_changeme, zoom: int, srs: EPSG = EPSG("EPSG:3857")):
    """Convert EPSG:4326 latitude and longitude to tile number of srs-projected tile pyramid.

    Args:
        xxx_todo_changeme: lat, lon - EPSG:4326 coordinates of a point
        zoom: zoomlevel of tile number
        srs: text string, specifying projection of tile pyramid
    """
    (lon, lat) = xxx_todo_changeme
    # zoom -= 1
    projected_bounds = from4326(projs[proj_alias.get(srs, srs)]["bounds"], srs)
    point = from4326((lon, lat), srs)
    point = [point[0] - projected_bounds[0], point[1] - projected_bounds[1]]
    # shifting (0,0)
    maxp = [
        projected_bounds[2] - projected_bounds[0],
        projected_bounds[3] - projected_bounds[1],
    ]
    point = [1.0 * point[0] / maxp[0], 1.0 * point[1] / maxp[1]]
    # normalizing
    return point[0] * (2**zoom), (1 - point[1]) * (2**zoom)


def to4326(line, srs: EPSG = EPSG("EPSG:3857")):
    """Transform line from srs to EPSG:4326 (convenience shortcut).

    Args:
        line: list of [lat0,lon0,lat1,lon1,...] or [(lat0,lon0),(lat1,lon1),...]
        srs: projection

    >>> point = _c4326t3857(1, 2, 27.6, 53.2)
    >>> to4326(point, EPSG("EPSG:3857"))
    [27.599999999999998, 53.20000000000001]

    >>> point = _c4326t3395(1, 2, 27.6, 53.2)
    >>> to4326(point, EPSG("EPSG:3395"))
    [27.599999999999998, 53.19999999779212]
    """
    return transform(line, srs, EPSG("EPSG:4326"))


def from4326(line, srs: EPSG = EPSG("EPSG:3857")):
    """Transform line from EPSG:4326 to srs (convenience shortcut).

    Args:
        line: list of [lat0,lon0,lat1,lon1,...] or [(lat0,lon0),(lat1,lon1),...]
        srs: projection

    >>> from4326((27.6, 53.2), EPSG("EPSG:3857"))
    [3072417.9458943508, 7020078.532642099]
    >>> from4326((27.6, 53.2), EPSG("EPSG:3395"))
    [3072417.9458943508, 6985840.123947986]
    """
    return transform(line, EPSG("EPSG:4326"), srs)


def transform(
    line: collections.abc.Sequence, srs1: EPSG, srs2: EPSG
) -> collections.abc.Sequence:
    """Convert bunch of coordinates from srs1 to srs2.

    Args:
        line: [lat0,lon0,lat1,lon1,...] or [(lat0,lon0),(lat1,lon1),...]
        srs1: source projection
        srs2: destination projection
    """
    srs1 = proj_alias.get(srs1, srs1)
    srs2 = proj_alias.get(srs2, srs2)
    if srs1 == srs2:
        return line
    if (srs1, srs2) in pure_python_transformers:
        func = pure_python_transformers[(srs1, srs2)]
    else:
        # func = pyproj.transform
        raise NotImplementedError
    line = list(line)
    serial = False
    if not isinstance(line[0], collections.abc.Sequence):
        serial = True
        l1 = list()
        while line:
            a = line.pop(0)
            b = line.pop(0)
            l1.append([a, b])
        line = l1
    ans: list[twms.bbox.Point | float] = list()
    pr1 = projs[srs1]["proj"]
    pr2 = projs[srs2]["proj"]
    for point in line:
        p = func(pr1, pr2, point[0], point[1])
        if serial:
            ans.append(p[0])
            ans.append(p[1])
        else:
            ans.append(p)
    return ans
