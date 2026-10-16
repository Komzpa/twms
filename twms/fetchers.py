import functools
import hashlib
import http
import http.client
import http.cookiejar
import io
import logging
import mimetypes
import os
import pathlib
import re
import tempfile
import textwrap
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import PIL.Image

import twms.config
import twms.projections

# import ssl
# ssl._create_default_https_context = ssl._create_unverified_context  # Disable context for gismap.by

logger = logging.getLogger(__name__)


class TileFile:
    """Filesystem cache.

      * TWMS stores tiles of 256x256 pixels
      * TWMS stores whole cache in single user-defined mimetype. If server returns tile with needed mimetype, original image is preserved, otherwise it will be recompressed
      * TWMS internally uses 'GLOBAL_WEBMERCATOR' grid, 'EPSG:3857' (formely known as 'EPSG:900913') projection, origin north-west (compatible with OpenStreetMap, mapproxy.org)
      * Same as SAS.Planet "Mobile Atlas Creator (MOBAC)" cache `cache_ma/{z}/{x}/{y}{ext}` 0,0 from the top left (nw)

    See:
      [1] https://en.wikipedia.org/wiki/Tiled_web_map
      [2] https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
      [3] https://josm.openstreetmap.de/wiki/SharedTileCache
    """

    def __init__(
        self,
        cache_dir: str,
        layer_id: str,
        mimetype: str,
        z: int,
        x: int,
        y: int,
        ttl: int | None = None,
    ):
        """Filesystem tile storage "cache_dir/layer_id/z/x/y.ext".

        Conforms SAS.Planet (with TNE), MOBAC, MapProxy 'tms' directory layout.

        TNE - tile not exist (got HTTP 404 or default tile for empty zones aka "dead tile")

        Args:
            cache_dir: relative path to tile cache
            layer_id: subdir for a single cache
            mimetype: One mimetype for whole layer
            z: tile coordinate (starts with zero)
            x: tile coordinate
            y: tile coordinate (positive)
            ttl: time-to-live, seconds or None
        """
        self.mimetype = mimetype
        self.ttl = ttl

        z, x, y = int(z), int(x), int(y)  # Prevent floats from messing up path
        prefix = pathlib.Path(cache_dir) / layer_id
        ext = mimetypes.guess_extension(self.mimetype)
        self.path = prefix / f"{z}/{x}/{y}{ext}"
        self.path_tne = prefix / f"{z}/{x}/{y}.tne"  # Tile not exists

    def __str__(self):
        return f"'{self.mimetype}' TTL: {self.ttl}, '{self.path}'"

    def get(self) -> pathlib.Path:
        """Get tile path.

        Must check `needs_fetch()` or `exists()` before.
        """
        # Locate file in file manager, calculate checksum, delete etc
        logger.debug(f"Cache hit 'file://{self.path}'")
        return self.path

    def set(self, blob: bytes | None = None) -> None:
        """Set image to cache and remove TNE.

        Args:
            blob: Image data. Create TNE file is None (tile not exists).
        """
        logger.debug(f"Saving {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if blob:
            fd, temporary_path = tempfile.mkstemp(
                dir=self.path.parent, prefix=f"{self.path.name}.tmp."
            )
            try:
                with os.fdopen(fd, "wb") as temporary_file:
                    temporary_file.write(blob)
                os.replace(temporary_path, self.path)
            except BaseException:
                os.unlink(temporary_path)
                raise
            self.path_tne.unlink(missing_ok=True)  # Remove TNE-files only there
        else:
            # Empty file, no timestamp inside to save disk space
            logger.warning(f"TILE NOT EXISTS {self.path_tne}")
            self.path_tne.touch()

    def delete(self) -> None:
        logger.info(f"Deleting '{self.path}', '{self.path_tne}'")
        self.path.unlink(missing_ok=True)
        self.path_tne.unlink(missing_ok=True)

    def exists(self) -> bool:
        """For filling map."""
        # Return (1, timestamp) in SQL
        return self.path.exists()

    def needs_fetch(self) -> bool:
        """Not exists in cache or TTL has been reached.

        Returns:
            True if not exists or st_mtime > TTL.
        """
        if self.path_tne.exists():
            if self.ttl and self.ttl < (time.time() - self.path_tne.stat().st_mtime):
                logger.info(f"TTL TNE reached: '{self.path_tne}'")
                return True
            else:
                logger.info(f"TNE '{self.path_tne}")
                return False
        # No else for TNE, try to check tile image

        if self.path.exists():
            if self.ttl and self.ttl < (time.time() - self.path.stat().st_mtime):
                logger.info(f"TTL reached: '{self.path}'")
                return True
            else:
                return False
        else:
            return True


def retry_opener(tries: int = 3, delay: int = 3, backoff: int = 2):
    """Retry on network error, pass HTTP errors.

    Args:
        tries: Retry attempts
        delay: initial delay between attempts, seconds
        backoff: Retry delay = delay * backoff
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = tries, delay
            while True:
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError:
                    raise  # Don't affect HTTP error code handling
                except urllib.error.URLError as err:
                    if mtries == 0:
                        logger.exception(func)
                        raise
                    # log "err.reason" and retry timeout
                    logger.debug(f"{err}: retry in {mdelay} seconds... '{args[1]}'")
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff

        return wrapper

    return decorator


class HttpSessionDirector:
    def __init__(
        self, headers: dict[str, str] = {}, timeout: float | None = None
    ):
        """Build HTTP opener with custom headers (session cookie) and context manager support.

        Args:
            headers: Replace all urllib headers. Useful to mock
            "User-Agent", "Referer", "Cookie".
            NB! "Connection: Keep-Alive" can't be replaced, as it not supported by urllib.

        Example:
            Read image and close the connection:

                http_session = HttpSessionDirector(
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/114.0",
                        "Referer": "https://example.com",
                        "Cookie": "cf_clearance=qwerty",
                    }
                )
                with http_session.get(url) as resp:
                    im = PIL.Image.open(resp)
                    im.show()
        """
        self.timeout = (
            twms.config.upstream_timeout if timeout is None else timeout
        )
        self.cj = http.cookiejar.CookieJar()
        # self.cj = http.cookiejar.MozillaCookieJar(filename="cookies.txt")
        # self.cj.load(filename="cookies.txt")

        self.opener_director = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
        )
        self.opener_director.addheaders = list(headers.items())  # Replace all headers

    @retry_opener()
    def get(
        self, *args, **kwargs
    ) -> http.client.HTTPResponse | urllib.error.HTTPError | None:
        """Same as 'urllib.request.urlopen' but with logging and HTTP error suppression.

        Returns:
            As HTTPError suppressed, method returns file-like
            HTTPResponse or HTTPError (io.BufferedIOBase subclasses) which
            holds body, HTTP status and response headers for further analysis.

        Raises:
            OSError subclasses, when fails to open URL several times.
        """
        kwargs.setdefault("timeout", self.timeout)
        try:
            return self.opener_director.open(*args, **kwargs)
        except urllib.error.HTTPError as resp:  # URLError subclass
            # Could pass no-op "urllib.request.HTTPErrorProcessor" subclass into
            # build_opener() to get rid of error handling, but leaving for logging
            # https://stackoverflow.com/questions/74680393/stop-urllib-request-from-raising-exceptions-on-http-errors
            logger.error(f"{resp}: '{args[0]}'")  # log with resp.msg aka err.reason
            return resp


class TileFetcher:
    """Load tiles by network or from local storage."""

    def __init__(self, layer_id: str):
        self.layer = twms.config.layers[layer_id]
        fetcher_names = ("tms", "tms_google_sat")
        if self.layer["fetch"] not in fetcher_names:
            raise ValueError(f"'fetch' must be one of {fetcher_names}")
        self.__worker = getattr(self, self.layer["fetch"])  # Choose fetcher
        self.http_session = HttpSessionDirector(
            headers=(twms.config.default_headers | self.layer["headers"]),
            timeout=self.layer.get("timeout"),
        )
        self.thread_pool = ThreadPoolExecutor(
            max_workers=twms.config.dl_threads_per_layer
        )
        # self._ic = Image.new("RGBA", (256, 256), self.layer["empty_color"])

    def fetch(self, z: int, x: int, y: int) -> PIL.Image.Image | None:
        """Fetch tile asynchronously.

        Returns:
            Image or None if no image can be served.
        """
        return self.thread_pool.submit(self.__worker, z, x, y).result()

    def tms(self, z: int, x: int, y: int) -> PIL.Image.Image | None:
        """Fetch tile by coordinates: network/cache.

        Function fetches image, checks it validity and detects actual
        image format (ignores server Content-Type). All tiles with
        Content-Type not matching default for this layer will be
        converted before saving to cache.

        Returns:
            Image in layer mimetype (converted if necessary).
        """
        tile_id = f"{self.layer['prefix']}/{z}/{x}/{y}"

        if z < self.layer["min_zoom"] or z > self.layer["max_zoom"]:
            logger.debug(f"Zoom limit {tile_id}")
            return None

        tile = TileFile(
            cache_dir=twms.config.tiles_cache,
            layer_id=self.layer["prefix"],
            z=z,
            x=x,
            y=y,
            mimetype=self.layer["mimetype"],
            ttl=self.layer["cache_ttl"],
        )

        # Fetching image
        if "remote_url" in self.layer and tile.needs_fetch():
            if "transform_tile_number" in self.layer:
                trans_z, trans_x, trans_y = self.layer["transform_tile_number"](z, x, y)
            else:
                trans_z, trans_x, trans_y = z, x, y

            # Placeholder substitution
            # TMS
            remote = self.layer["remote_url"].replace("{z}", str(trans_z))
            remote = remote.replace("{x}", str(trans_x))
            remote = remote.replace("{y}", str(trans_y))
            # Avoid negative zoom errors i.e. when`"transform_tile_number": lambda z, x, y: (z - 8, x, y)`
            if "{-y}" in remote:
                remote = remote.replace(
                    "{-y}", str(tile_slippy_to_tms(trans_z, trans_x, trans_y)[2])
                )
            # Bing quadkey
            remote = remote.replace("{q}", tile_to_quadkey(trans_z, trans_x, trans_y))

            # WMS support, no difference with TMS except missing TNE feature
            # Some considerations:
            #   * Biger tile request (e.g. 512x512)?
            #   * Using different 'wms_proj' parameter, as server may be broken
            if "{bbox}" in remote:
                proj = self.layer["proj"]
                tile_bbox = "{},{},{},{}".format(
                    *twms.projections.from4326(
                        twms.projections.bbox_by_tile(z, x, y, proj),
                        proj,
                    )
                )
                remote = remote.replace("{bbox}", tile_bbox)
                remote = remote.replace("{width}", "256")
                remote = remote.replace("{height}", "256")
                remote = remote.replace("{proj}", proj)

            # Fetching tiles
            try:
                # Got response, need to verify content
                logger.info(f"{tile_id}: FETCHING {remote}")
                with self.http_session.get(remote) as remote_resp:
                    resp_bytes = remote_resp.read()  # Doesn't support seek()
                    resp_md5 = hashlib.md5(resp_bytes).hexdigest()
                    resp_buf = io.BytesIO(resp_bytes)
                    # Just 404, as decent server would respond
                    if remote_resp.status == http.HTTPStatus.NOT_FOUND:
                        tile.set()
                        return None
                    elif remote_resp.status == http.HTTPStatus.FORBIDDEN:
                        return None
                    # Sometimes tile missing, but server reports other code instead 404
                    if "dead_tile" in self.layer:
                        if (
                            "http_status" in self.layer["dead_tile"]
                            and remote_resp.status
                            == self.layer["dead_tile"]["http_status"]
                        ):
                            logger.warning(f"{tile_id}: TNE - {remote_resp}")
                            tile.set()
                            return None

                        # Sometimes server returns same dummy file instead of empty HTTP response
                        # Compare bytestring with dead tile hash
                        if (
                            "md5" in self.layer["dead_tile"]
                            and resp_md5 in self.layer["dead_tile"]["md5"]
                        ):
                            # Tile is recognized as empty
                            # An example http://ecn.t0.tiles.virtualearth.net/tiles/a120210103101222.jpeg?g=0
                            # SASPlanet writes empty files with '.tne' ext
                            logger.warning(f"{tile_id}: TNE - dead tile checksum")
                            tile.set()
                            return None

                    # Catching invalid pictures
                    if not resp_bytes:
                        logger.warning(f"{tile_id}: empty response")
                        # tile.set()

                    try:
                        with PIL.Image.open(resp_buf) as im:
                            im.load()  # Validate image
                            # TNE based on histogram (from WMS)
                            # if im.histogram() == self._ic.histogram():
                            #     logger.debug(f"{tile_id}: TNE - empty histogram")
                            #     tile.set()
                            #     return None

                            # All well, save tile to cache
                            # Preserving original image if possible, as encoding is lossy
                            # Storing all images into one format, just like SAS.Planet does
                            if im.get_format_mimetype() == self.layer["mimetype"]:
                                tile.set(resp_bytes)
                            else:
                                logger.warning(
                                    f"{tile_id}: converting '{im.get_format_mimetype()}' to '{self.layer['mimetype']}'"
                                )
                                tile.set(im_convert(im, self.layer["mimetype"]))
                            return im
                    except PIL.UnidentifiedImageError:
                        logger.error(f"{tile_id}: failed to parse response as image")
                        logger.debug(
                            textwrap.dedent(
                                f"""
                            {tile_id}: invalid image {remote_resp.status}: {remote_resp.msg} - {remote_resp.reason} {remote_resp.url}
                            {remote_resp.headers}
                            {remote_resp}
                            """
                            )
                            + f"md5sum: '{resp_md5}'"
                        )
                        # try:
                        #     logger.debug(remote_bytes.decode("utf-8"))
                        # except UnicodeDecodeError:
                        #     logger.debug(remote_bytes)
                        # if logger.getLogger().getEffectiveLevel() == logger.DEBUG:
                        #     with open('err.htm', mode='wb') as f:
                        #         f.write(remote_bytes)
            except urllib.error.URLError as err:
                # Nothing we can do: no connection, so cannot guess TNE or not
                logger.error(f"{tile_id} URLError '{err}'")
            logger.error(f"{tile_id}: tile fetch failed")

        # If fetching failed
        if tile.exists():
            try:
                with PIL.Image.open(tile.get()) as im:
                    im.load()
                    return im
            except OSError:
                logger.error(f"{tile_id}: failed to parse image from cache")
                # tile.delete()  # Cached tile is broken - remove it

        logger.error(f"{tile_id}: no tile")
        return None

    def tms_google_sat(self, z: int, x: int, y: int) -> PIL.Image.Image:
        """Construct template URI with version from JS API.

        May be use different servers in future:
        https://khms0.google.com/kh/v=889?x=39595&y=20473&z=16
        https://khms3.google.com/kh/v=889?x=39595&y=20472&z=16

        # No 'v=?' required?
        https://mt0.google.com/vt/lyrs=s@0&hl=en&z={z}&x={x}&y={y}
        """
        if "remote_url" not in self.layer:
            try:
                with self.http_session.get(
                    "https://maps.googleapis.com/maps/api/js"
                ) as resp:
                    match = re.search(
                        r"https://khms\d+.googleapis\.com/kh\?v=(\d+)",
                        resp.read().decode("utf-8"),
                    )
                    if match and match.group(1):
                        self.layer[
                            "remote_url"
                        ] = f"https://kh.google.com/kh/v={match.group(1)}?x={{x}}&y={{y}}&z={{z}}"
                        logger.info(
                            f"Setting new {self.layer['name']} URI {self.layer['remote_url']}"
                        )
                    else:
                        raise ValueError("Cannot parse 'v=' from maps_googleapis_js")
            except urllib.error.URLError:
                pass

        # URL version can expiry, reset if no image
        # Though it is not only possible cause of None response
        im = self.tms(z, x, y)
        if "remote_url" in self.layer and not im:
            del self.layer["remote_url"]
        return im


def tile_to_quadkey(z: int, x: int, y: int) -> str:
    """Transform tile coordinates to a Bing quadkey.

    Slippy map tiles cache numeration starts from 0 level with one tile. On 1 level four tiles etc
    Bing uses quadkey tile coordinates, so minimal cache level is 1 (four tiles). Single tile at zero level not addressed.

    https://docs.microsoft.com/en-us/bingmaps/articles/bing-maps-tile-system
    https://github.com/buckhx/QuadKey/blob/master/quadkey/tile_system.py

    Args:
        z: zoom, starts from zero

    Returns:
        Quadkey string

    Examples
    --------
    >>> tile_to_quadkey(1,0,0)
    '0'
    >>> tile_to_quadkey(4, 9, 5)
    '1203'
    >>> tile_to_quadkey(16, 38354, 20861)
    '1203010313232212'
    """
    quadkey = list()
    for i in range(z):
        bit = z - i
        digit = ord("0")
        mask = 1 << (bit - 1)
        if (x & mask) != 0:
            digit += 1
        if (y & mask) != 0:
            digit += 2
        quadkey.append(chr(digit))
    return "".join(quadkey)


def tile_slippy_to_tms(z: int, x: int, y: int) -> tuple[int, int, int]:
    """Convert Slippy map coordinate system to OSGeo TMS `{-y}`.

    https://josm.openstreetmap.de/wiki/Maps

    >>> tile_slippy_to_tms(4, 3, 2)
    (4, 3, 13)
    >>> tile_slippy_to_tms(10, 10, 10)
    (10, 10, 1013)
    """
    return z, x, (1 << z) - y - 1


def im_convert(im: PIL.Image.Image, mimetype: str) -> bytes:
    """Convert Pillow image to requested mimetype."""
    # Exif-related code not documented, Pillow can change behavior
    output_quality = 75
    output_progressive = True
    exif = PIL.Image.Exif()
    exif[0x0131] = twms.config.wms_name  # ExifTags.TAGS['Software']

    img_buf = BytesIO()

    if mimetype == "image/jpeg":
        im = im.convert("RGB")
        im.save(
            img_buf,
            "JPEG",
            quality=output_quality,
            progressive=output_progressive,
            exif=exif,
        )
    elif mimetype == "image/png":
        im.save(
            img_buf,
            "PNG",
            progressive=output_progressive,
            optimize=False,
            exif=exif,
        )
    elif mimetype == "image/gif":
        im.save(
            img_buf,
            "GIF",
            quality=output_quality,
            progressive=output_progressive,
            exif=exif,
        )
    else:
        im = im.convert("RGB")
        im.save(
            img_buf,
            mimetype.split("/")[1],
            exif=exif,
        )
    return img_buf.getvalue()
