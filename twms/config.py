"""TWMS config file."""

import os
import pathlib
import sqlite3
import typing

import twms
import twms.bbox


class DefaultDict(dict):
    """Dict with default key values."""

    def __init__(self, defaults: dict, *args, **kwargs):
        """Init with default dict and incomplete dict.

        Missing 'in' returns False, but '__getitem__' returns default value.

        Args:
            defaults: Dict with default parameters.
        """
        super().__init__(*args, **kwargs)
        self.defaults = defaults

    def __missing__(self, key):
        return self.defaults[key]


def extract_cookie(db_fp: str | pathlib.Path, name: str, host: str) -> tuple:
    """Return cookie with "expired" timestamp from Firefox database.

    Args:
        db_fp: Firefox cookie database path like
            "~/.mozilla/firefox/aaaaaaaa.default-release/cookies.sqlite"

    Returns:
        Tuple: (expity_timestamp, cookie_str)
    """
    # Firefox locks db, so using immutable mode to read
    con = sqlite3.connect(f"file:{db_fp}?immutable=1", uri=True)
    cur = con.execute(
        """
        SELECT expiry, name || '=' || value AS cookie
        FROM moz_cookies
        WHERE host = :host AND name = :name
        """,
        dict(name=name, host=host),
    )
    res = cur.fetchone()
    con.close()
    return res


def get_latest_cookie(name: str, host: str) -> str:
    """Lookup for a latest cookie from all Firefox profiles.

    Args:
        name: cookie name
        host: cookie host
    """
    all_cookies = dict()
    ff_profile_dir = pathlib.Path("~/.mozilla/firefox/").expanduser()
    for ff_cookie_db_fp in ff_profile_dir.glob("*/cookies.sqlite"):
        if cookie := extract_cookie(ff_cookie_db_fp, name=name, host=host):
            all_cookies[cookie[0]] = cookie[1]
    if all_cookies:
        return all_cookies[max(all_cookies)]
    else:
        return ""


wms_name = f"twms {twms.__version__}"
host = "127.0.0.1"
port = 8080
service_url = f"http://{host}:{port}"
service_wms_url = service_url + "/wms"
service_wmts_url = service_url + "/wmts"

# NB! "Connection: Keep-Alive" not supported by urllib
default_headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/114.0",
}


# Cloudflare cookie associated with User-Agent, IP
dzzby_headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/114.0",
    "Referer": "https://www.dzz.by/izuchdzz/",
    "Cookie": get_latest_cookie(name="cf_clearance", host=".dzz.by"),
}

# There may be more appropriate place for a cache, like `~/.cache/osm/tiles/`
tiles_cache = os.path.expanduser("~/dev/gis/sasplanet/SAS.Planet/cache_ma/")
# tiles_cache = os.path.expanduser("~/dev/gis/sasplanet/SAS.Planet/cache_test/")

ram_cache_tiles = 2048  # Number of tiles in RAM cache
dl_threads_per_layer = 5

upstream_timeout = 30  # Seconds; override per layer with its "timeout" setting.
# WMS GetCapabilities
default_layers = ""  # layer(s) to show when no layers given explicitly
max_height = 4095  # WMS maximal allowed requested height
max_width = 4095  # WMS maximal allowed requested width


layer_defaults = {
    # Mandatory paramaters
    # name           str - visible layer name
    # prefix         str - unique cache tile subdirectory name
    # Optional paramaters
    "mimetype": "image/jpeg",  # str Tiles will be stored and served in this mimetype, converted if necessary
    "overlay": False,  # bool Transparent hybrid map
    "proj": "EPSG:3857",  # str EPSG code of layer tiles projection.
    "empty_color": "#ffffff",  # PIL color string. If this layer is overlayed over another, this color will be considered transparent. Also used for dead tile detection in fetchers.WMS
    "cache_ttl": None,  # int cache expiration time
    # WGS84 (EPSG:4326) (min-lon, min-lat, max-lon, max-lat; lower left and upper right corners; W, S, E, N) no wms fetching will be performed outside this bbox.
    "bounds": (-180.0, -85.0511287798, 180.0, 85.0511287798),
    # "dead_tile": { dict, if given, loaded tiles matching pattern won't be saved.
    #     "md5": {}, # set of md5sum hashes of that tile
    #     "size" tile size in bytes
    #     "sha256"
    #     "http_status": 503  # TNE by HTTP status code
    # }
    "fetch": "tms",  # str name of the function that fetches tiles. func(z, x, y, layer_id) -> Imaga.Image | None
    "headers": dict(),  # Headers and authentication cookies
    "min_zoom": 0,  # >= zoom to load
    "max_zoom": 19,  # <= # Load tiles with equal or less zoom. Can be set with 'max_zoom' per layer. [19] 30 cm resolution - best Maxar satellite resolution at 2021
    "scalable": False,  # bool Could zN tile be constructed of four z(N+1) tiles. Construct tile from available better ones. If False, tWMS will use nearest zoom level
    # "provider_url"  # Imagery provider webside URL for imagery overview page.
    # "remote_url"  # str Template URL. Should contain placeholders, e.g. {z}, {x}, {y}, {bbox},  {width}, {height}, {proj} for TMS/WMS, see fetchers.TileFetcher.tms.
    # "transform_tile_number": lambda z, x, y: (z, x, y),  # function that returns tuple that will be substituted into **remote_url**. If omitted, (z, x, y) tuple is used.
}

# Other WMTS configs https://github.com/bertt/wmts
layers: dict[str, dict[str, typing.Any]] = {
    "yasat": {
        "name": "Yandex Satellite",
        "provider_url": "https://yandex.ru/maps/",
        "prefix": "yasat",
        "proj": "EPSG:3395",  # WGS84 World mercator, ellipsoid
        "remote_url": "https://core-sat.maps.yandex.net/tiles?l=sat&x={x}&y={y}&z={z}&scale=1&lang=ru_RU",
        "cache_ttl": 60 * 60 * 24 * 30,  # Month
    },
    "yamapng": {
        "name": "Yandex Map",
        "provider_url": "https://yandex.ru/maps/",
        "prefix": "yamapng",
        "proj": "EPSG:3395",
        "mimetype": "image/png",
        "remote_url": "https://core-renderer-tiles.maps.yandex.net/tiles?l=map&x={x}&y={y}&z={z}&scale=1&lang=ru_RU",
        "cache_ttl": 60 * 60 * 24 * 30,  # Month
    },
    "yahyb": {
        "name": "Yandex Hybrid RU",
        "provider_url": "https://yandex.ru/maps/",
        "prefix": "yahyb",  # "maps.yandex.com.Hybrid" for english tiles
        "proj": "EPSG:3395",
        "mimetype": "image/png",
        "overlay": True,
        "min_zoom": 1,
        "max_zoom": 20,  # Small POI like fitness stations
        "remote_url": "https://core-renderer-tiles.maps.yandex.net/tiles?l=skl&x={x}&y={y}&z={z}&scale=1&lang=ru_RU",
        "cache_ttl": 60 * 60 * 24 * 30,  # Month
    },
    "yandextracks": {
        "name": "Yandex Tracks",
        "provider_url": "https://n.maps.yandex.ru",
        "prefix": "yandextracks",
        "proj": "EPSG:3395",
        "mimetype": "image/png",
        # https://core-gpstiles.maps.yandex.net/tiles?style=red_combined&x={x}&y={y}&z={z}
        "remote_url": "https://core-gpstiles.maps.yandex.net/tiles?style=point&x={x}&y={y}&z={z}",
        "min_zoom": 11,
        "max_zoom": 17,
        "cache_ttl": 60 * 60 * 24 * 30,  # Month
    },
    "sat": {
        "name": "Google Satellite",
        "provider_url": "https://www.google.com/maps/",
        "prefix": "sat",
        # "fetch": "tms_google_sat",
        "remote_url": "https://mt0.google.com/vt/lyrs=s@0&z={z}&x={x}&y={y}",
        "cache_ttl": 60 * 60 * 24 * 30,  # Month
    },
    "Both": {
        "name": "Google Hybrid RU",
        "provider_url": "https://www.google.com/maps/",
        "prefix": "Both",
        "mimetype": "image/png",
        "remote_url": "https://mt0.google.com/vt/lyrs=h@0&z={z}&x={x}&y={y}&hl=ru",
        "min_zoom": 2,
        "cache_ttl": 60 * 60 * 24 * 30,  # Month
    },
    # First available top left tile https://ecn.t0.tiles.virtualearth.net/tiles/a0.jpeg?g=0
    # Dead tile https://ecn.t0.tiles.virtualearth.net/tiles/a120210103100213.jpeg?g=0
    "vesat": {
        "name": "Bing Satellite",
        "provider_url": "https://www.bing.com/maps?style=h",
        "prefix": "vesat",
        "remote_url": "https://ecn.t0.tiles.virtualearth.net/tiles/a{q}.jpeg?g=0",
        "min_zoom": 1,  # Don't serve z0/x0/y0 (400 Bad Request for "https://ecn.t0.tiles.virtualearth.net/tiles/a.jpeg?g=0")
        # "max_zoom": 19,
        "cache_ttl": 60 * 60 * 24 * 30,  # Month
        # Check against known size in bytes and md5 hash
        "dead_tile": {
            "size": 1033,
            "md5": {"c13269481c73de6e18589f9fbc3bdf7e"},
            "sha256": "45d35034a62d30443e492851752f67f439b95a908fce54de601f7373fcb7ab05",
        },
    },
    "osmmapMapnik": {
        "name": "OSM Mapnik",
        "provider_url": "https://www.openstreetmap.org/",
        "prefix": "osmmapMapnik",
        "mimetype": "image/png",
        "max_zoom": 19,
        "remote_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",  # URL template with placeholders
        "headers": {"Referer": "https://www.openstreetmap.org/"},
        "empty_color": "#F1EEE8",
        "cache_ttl": 60 * 60 * 24 * 30,  # 1 month
    },
    "osm_gps_tile": {
        "name": "OSM GPS Traces",
        "provider_url": "https://www.openstreetmap.org/",
        "prefix": "osm_gps_tile",
        "mimetype": "image/png",
        "overlay": True,
        "remote_url": "https://gps-tile.openstreetmap.org/lines/{z}/{x}/{y}.png",
        "headers": {"Referer": "https://www.openstreetmap.org/"},
        "cache_ttl": 60 * 60 * 24 * 30,  # 1 month
    },
    # 'addr_ks' - red dot - капитальное строение (КС)
    # yellow dot - Незавершенное законсервированное капитальное строение (НЗКС)
    # green dot - земельный участок (ЗУ)
    "ncaby_radr": {
        "name": "nca.by Capital buildings and addresses",
        "provider_url": "http://vl.nca.by/",
        "prefix": "ncaby_radr",
        "mimetype": "image/png",
        "bounds": (23.16722, 51.25930, 32.82244, 56.18162),  # Belarus
        "min_zoom": 15,
        "remote_url": "http://gisserver3.nca.by:8080/geoserver/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&FORMAT=image/png&TRANSPARENT=true&layers=prod:radr&propertyName=obj_name,elementtyp,elementnam,addr_label,geom&TILED=true&STYLES=addr_ks&WIDTH={width}&HEIGHT={height}&CRS={proj}&BBOX={bbox}",
        "cache_ttl": 60 * 60 * 24 * 30,  # 1 month
    },
    # "geoby_mapserver": {
    #     "name": "geo.by Belgeodesy Map",
    #     "provider_url": "https://geo.by/navigation/map",  # ? https://geo.maps.by/
    #     "prefix": "geoby_mapserver",
    #     "mimetype": "image/png",
    #     "bounds": (23.16722, 51.25930, 32.82244, 56.18162),  # Belarus
    #     "remote_url": "https://mapserver.geo.by/mapcache/?SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1&LAYERS=mapserver_tileset&STYLES=&FORMAT=image/png&TRANSPARENT=true&HEIGHT={height}&WIDTH={width}&SRS={proj}&BBOX={bbox}",
    #     "headers": {"Referer": "https://geo.by/navigation/map"},
    #     "cache_ttl": 60 * 60 * 24 * 30,  # 1 month
    # },
    # "landsat":  {
    #      "name": "Landsat from onearth.jpl.nasa.gov",
    #      "prefix": "landsat",
    #      string without srs, height, width and bbox
    #      "remote_url": "https://onearth.jpl.nasa.gov/wms.cgi?request=GetMap&layers=global_mosaic&styles=&format=image/jpeg&",
    #      "max_zoom": 14,
    #      "proj": "EPSG:4326",
    #      "wms_proj": "EPSG:4326",  # what projection to ask from wms
    # },
    # "navitel":  {
    #     "name": "Navitel Navigator Maps",
    #     "prefix": "Navitel",
    #     "mimetype": "image/png",
    #     "remote_url": "https://map.navitel.su/navitms.fcgi?t=%08i,%08i,%02i";,
    #     "transform_tile_number": lambda z,x,y: (x, 2**(z-1)-y-1, z-1),
    #     "min_zoom": 5,
    #     "bounds": (17.999999997494381, 39.999999995338634, 172.99999997592218, 77.999999996263981),
    # },
    # "DGsat": {
    #      "name": "Digital Globe Satellite",
    #      "prefix": "DGsat",
    #      # Could add "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/16/20867/38349"
    # },
    # "maxar_prem": {
    #     "name": "Maxar Premuim",
    #     "provider_url": "https://www.maxar.com/",
    #     "prefix": "maxar_prem",
    #     "max_zoom": 18,  # Looks like artificial restriction
    #     # API key from JOSM
    #     "remote_url": "https://services.digitalglobe.com/earthservice/tmsaccess/tms/1.0.0/DigitalGlobe:ImageryTileService@EPSG:3857@jpg/{z}/{x}/{-y}.jpg?connectId=fa014fbc-6cbe-4b6f-b0ca-fbfb8d1e5b7d&foo=premium",
    # },
    # "irs":  {
    #     "name": "Kosmosnimki.ru IRS Satellite",
    #     "prefix": "irs",
    #     "remote_url": "https://maps.kosmosnimki.ru/TileSender.ashx?ModeKey=tile&MapName=F7B8CF651682420FA1749D894C8AD0F6&LayerName=950FA578D6DB40ADBDFC6EEBBA469F4A&z=%s&x=%s&y=%s";,
    #     "transform_tile_number": lambda z,x,y: (z-1,int(-((int(2**(z-1)))/ 2)+x),int(-((int(2**(z-1)))/ 2)+ int(2**(z-1)-(y+1)))),
    #     "dead_tile": {"size": 0, "md5": {"d41d8cd98f00b204e9800998ecf8427e"}, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
    #     "min_zoom": 2,
    #     "max_zoom": 16,
    #     "empty_color": "#000000",
    #     "proj": "EPSG:3395",
    #     "bounds": (26.0156238531320340,40.7707274153093520,69.257808718487752,67.610652011923932),
    # },
    # "yhsat": {
    #      "name": "Yahoo Satellite",
    #      "prefix": "yhsat",
    #      "remote_url": "https://aerial.maps.yimg.com/ximg?v=1.8&t=a&s=256&r=1&x=%s&y=%s&z=%s",
    #      "transform_tile_number": lambda z,x,y: (x,((2**(z-1)/2)-1)-y,z),
    #      "min_zoom": 2,
    #      "max_zoom": 18,
    # },
    "dzzby_orthophoto": {
        # [19] 30 cm most of Belarus
        # [20] 15 cm Minsk
        #     20 top for orthophoto, but in most places it just blurred 19
        # [21]
        # [22] 7.5~5 cm Unmanned airway vehicle "Геоскан-201" for садоводческие товарищества and towns
        #     22 top for UAV
        "name": "dzz.by (Belarus) Aerial",
        "provider_url": "https://www.dzz.by/izuchdzz/",  # https://beldzz.by/
        "prefix": "dzzby_orthophoto",
        "bounds": (23.16722, 51.25930, 32.82244, 56.18162),  # Belarus
        # nca.by has sane proxy (valid 404, SSL certificate)
        # https://api.nca.by/gis/dzz/tile/11/41342/76532
        # "remote_url": "https://api.nca.by/gis/dzz/tile/{z}/{y}/{x}",  # GeoIP 403
        # dzz.by + Cloudflare
        # https://www.dzz.by/Java/proxy.jsp?https://www.dzz.by/arcgis/rest/services/georesursDDZ/Belarus_Web_Mercator_new/ImageServer/tile/11/41342/76532
        "headers": dzzby_headers,
        "remote_url": "https://www.dzz.by/Java/proxy.jsp?https://www.dzz.by/arcgis/rest/services/georesursDDZ/Belarus_Web_Mercator_new/ImageServer/tile/{z}/{y}/{x}",
        # https://gismap.by invalid certificate, weird 404 handling
        # "headers": {"Referer": "https://gismap.by/next/"},  # 403 without SSL
        # "remote_url": "https://gismap.by/next/proxy/proxy.ashx?https://www.dzz.by/arcgis/rest/services/georesursDDZ/Belarus_Web_Mercator_new/ImageServer/tile/{z}/{y}/{x}",
        # ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1123)
        "transform_tile_number": lambda z, x, y: (z - 6, x, y),
        "min_zoom": 6,
        "max_zoom": 19,  # max_zoom is 20, but in most places it just blurred 19
        # "scalable": True,
        "dead_tile": {"http_status": 502, "md5": {"d95150a258cdd8d2c6282c406c287b81"}},
    },
    # Not working at 2023-06-25
    "dzzby_BPLA_2021": {
        "name": "dzz.by (Belarus) dzzby_BPLA_2021",
        "provider_url": "https://www.dzz.by/izuchdzz/",  # https://beldzz.by/
        "prefix": "dzzby_BPLA_2021",
        # "mimetype": "image/png",  # Most tiles are transparent
        "bounds": (23.16722, 51.25930, 32.82244, 56.18162),  # Belarus
        # "headers": dzzby_headers,
        # "remote_url": "https://www.dzz.by/Java/proxy.jsp?https://www.dzz.by/arcgis/rest/services/Orthomosaics/BPLA_WGS1984/ImageServer/tile/{z}/{y}/{x}",
        "transform_tile_number": lambda z, x, y: (z - 8, x, y),  # 0-8 zooms are missing
        "min_zoom": 8,
        "max_zoom": 22,  # Has tiles on 22 level, but mostly 20
        # "scalable": True,
    },
    "dzzby_BPLA_2022": {
        "name": "dzz.by (Belarus) dzzby_BPLA_2022",
        "provider_url": "https://www.dzz.by/izuchdzz/",  # https://beldzz.by/
        "prefix": "dzzby_BPLA_2022",
        "mimetype": "image/png",  # Most tiles are transparent
        "bounds": (23.16722, 51.25930, 32.82244, 56.18162),  # Belarus
        "headers": dzzby_headers,
        "remote_url": "https://www.dzz.by/Java/proxy.jsp?https://www.dzz.by/arcgis/rest/services/georesursDDZ/BPLA_Web_Mercator_2022/ImageServer/tile/{z}/{y}/{x}",
        "transform_tile_number": lambda z, x, y: (z - 8, x, y),
        "min_zoom": 8,
        "max_zoom": 22,
        "dead_tile": {
            "http_status": 502,
            "md5": {
                "d95150a258cdd8d2c6282c406c287b81",
                "8c77c9de578e056b39c1531e1c82c60e",
            },
        },
        # "scalable": True,
    },
}


# Populate with default values
for k, v in layers.items():
    # layers[k] = layer_defaults | v
    layers[k] = DefaultDict(layer_defaults, v)
