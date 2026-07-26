# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

import filecmp
import hashlib
import math
import os
import sys
import threading
import time
from io import BytesIO
from urllib.request import urlopen

import config
import projections
from PIL import Image
from twms.image_compat import resampling_lanczos


fetching_now = {}
thread_responses = {}
zhash_lock = {}


def _cache_stem(z, x, y, this_layer):
    return (
        config.tiles_cache
        + this_layer["prefix"]
        + "/z%s/%s/x%s/%s/y%s." % (z, x // 1024, x, y // 1024, y)
    )


class TileCache:
    """Small filesystem cache helper.

    This keeps TWMS' historical zN/NNN/xN/NNN/yN.ext layout, but adds the useful
    cache semantics from Radioxoma's fork: TTL checks, readable TNE markers,
    stale-cache fallback, and atomic file replacement.
    """

    def __init__(self, z, x, y, this_layer):
        self.layer = this_layer
        self.cached = this_layer.get("cached", True)
        if self.cached:
            self.stem = _cache_stem(z, x, y, this_layer)
            self.path = self.stem + this_layer["ext"]
            self.tne_path = self.stem + "tne"
            self.lock_path = self.stem + "lock"
        else:
            self.stem = None
            self.path = None
            self.tne_path = None
            self.lock_path = None

    def _fresh(self, path):
        if not os.path.exists(path):
            return False
        ttl = self.layer.get("cache_ttl")
        if not ttl:
            return True
        return time.time() - os.path.getmtime(path) <= ttl

    def needs_fetch(self):
        if not self.cached:
            return True
        if self._fresh(self.tne_path):
            return False
        if self._fresh(self.path):
            return False
        return True

    def open_image(self, include_stale=False):
        if not self.cached or not os.path.exists(self.path):
            return None
        if not include_stale and not self._fresh(self.path):
            return None
        return Image.open(self.path)

    def ensure_parent(self):
        parent = os.path.dirname(self.stem)
        if parent and not os.path.exists(parent):
            os.makedirs(parent)

    def acquire(self):
        if not self.cached:
            return False
        self.ensure_parent()
        os.mkdir(self.lock_path)
        return True

    def release(self):
        if self.cached and os.path.exists(self.lock_path):
            os.rmdir(self.lock_path)

    def wait_for_peer(self):
        for _ in range(20):
            time.sleep(0.1)
            if not os.path.exists(self.lock_path):
                if self._fresh(self.tne_path):
                    return None
                return self.open_image()
        return None

    def write_bytes(self, contents):
        if not self.cached:
            return
        tmp_path = self.path + ".tmp.%s" % os.getpid()
        with open(tmp_path, "wb") as tile_file:
            tile_file.write(contents)
        os.replace(tmp_path, self.path)
        if os.path.exists(self.tne_path):
            os.remove(self.tne_path)

    def save_image(self, image):
        if not self.cached:
            return
        tmp_path = self.path + ".tmp.%s" % os.getpid()
        image.save(tmp_path)
        os.replace(tmp_path, self.path)
        if os.path.exists(self.tne_path):
            os.remove(self.tne_path)

    def mark_tne(self):
        if not self.cached:
            return
        self.ensure_parent()
        if os.path.exists(self.path):
            os.remove(self.path)
        with open(self.tne_path, "wb") as tne:
            tne.write(b"")


def fetch(z, x, y, this_layer):
    zhash = repr((z, x, y, this_layer))
    try:
        zhash_lock[zhash] += 1
    except KeyError:
        zhash_lock[zhash] = 1
    if zhash not in fetching_now:
        atomthread = threading.Thread(
            None, threadwrapper, None, (z, x, y, this_layer, zhash)
        )
        atomthread.start()
        fetching_now[zhash] = atomthread
    if fetching_now[zhash].is_alive():
        fetching_now[zhash].join()
    resp = thread_responses[zhash]
    zhash_lock[zhash] -= 1
    if not zhash_lock[zhash]:
        del thread_responses[zhash]
        del fetching_now[zhash]
        del zhash_lock[zhash]
    return resp


def threadwrapper(z, x, y, this_layer, zhash):
    try:
        thread_responses[zhash] = this_layer["fetch"](z, x, y, this_layer)
    except OSError:
        for i in range(20):
            time.sleep(0.1)
            try:
                thread_responses[zhash] = this_layer["fetch"](z, x, y, this_layer)
                return
            except OSError:
                continue
        thread_responses[zhash] = None


def WMS(z, x, y, this_layer):
    if "max_zoom" in this_layer:
        if z >= this_layer["max_zoom"]:
            return None
    wms = this_layer["remote_url"]
    req_proj = this_layer.get("wms_proj", this_layer["proj"])
    width = 384  # using larger source size to rescale better in python
    height = 384
    cache = TileCache(z, x, y, this_layer)
    tile_bbox = "bbox=%s,%s,%s,%s" % tuple(
        projections.from4326(projections.bbox_by_tile(z, x, y, req_proj), req_proj)
    )

    wms += tile_bbox + "&width=%s&height=%s&srs=%s" % (width, height, req_proj)
    if this_layer.get("cached", True) and not cache.needs_fetch():
        return cache.open_image()
    locked = False
    if this_layer.get("cached", True):
        try:
            locked = cache.acquire()
        except OSError:
            return cache.wait_for_peer()
    try:
        try:
            im = Image.open(BytesIO(urlopen(wms).read()))
        except OSError:
            stale = cache.open_image(include_stale=True)
            if stale is not None:
                return stale
            return False
        if width != 256 and height != 256:
            im = im.resize((256, 256), resampling_lanczos(Image))
        im = im.convert("RGBA")

        if this_layer.get("cached", True):
            ic = Image.new(
                "RGBA",
                (256, 256),
                this_layer.get("empty_color", config.default_background),
            )
            if im.histogram() == ic.histogram():
                cache.mark_tne()
                return False
            cache.save_image(im)
        return im
    finally:
        if locked:
            cache.release()


def Tile(z, x, y, this_layer):
    global OSError, IOError
    d_tuple = z, x, y
    if "max_zoom" in this_layer:
        if z >= this_layer["max_zoom"]:
            return None
    if "transform_tile_number" in this_layer:
        d_tuple = this_layer["transform_tile_number"](z, x, y)

    remote = this_layer["remote_url"] % d_tuple
    cache = TileCache(z, x, y, this_layer)
    if this_layer.get("cached", True) and not cache.needs_fetch():
        return cache.open_image()
    locked = False
    if this_layer.get("cached", True):
        try:
            locked = cache.acquire()
        except OSError:
            return cache.wait_for_peer()
    try:
        try:
            contents = urlopen(remote).read()
            im = Image.open(BytesIO(contents))
        except OSError:
            stale = cache.open_image(include_stale=True)
            if stale is not None:
                return stale
            return False
        if "dead_tile" in this_layer and _is_dead_tile(contents, this_layer["dead_tile"]):
            cache.mark_tne()
            return False
        if this_layer.get("cached", True):
            cache.write_bytes(contents)
        return im
    finally:
        if locked:
            cache.release()


def _is_dead_tile(contents, dead_tile):
    if isinstance(dead_tile, dict):
        if "size" in dead_tile and len(contents) != dead_tile["size"]:
            return False
        if "md5" in dead_tile:
            md5 = hashlib.md5(contents).hexdigest()
            if md5 not in dead_tile["md5"]:
                return False
        if "sha256" in dead_tile:
            sha256 = hashlib.sha256(contents).hexdigest()
            if sha256 != dead_tile["sha256"]:
                return False
        return True
    try:
        return contents == open(dead_tile, "rb").read()
    except IOError:
        return False
