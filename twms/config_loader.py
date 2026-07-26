# -*- coding: utf-8 -*-

import importlib.machinery
import importlib.util
import mimetypes
import os
import sys


class LayerConfig(dict):
    """Layer mapping that falls back to shared ``layer_defaults``.

    TWMS layer configuration is intentionally plain Python.  This wrapper keeps
    old ``layer["key"]`` callers working while letting new configs declare
    common defaults once.
    """

    def __init__(self, defaults, values):
        super().__init__(values)
        self.defaults = defaults

    def __missing__(self, key):
        if key in self.defaults:
            return self.defaults[key]
        raise KeyError(key)

    def get(self, key, default=None):
        if key in self:
            return super().get(key)
        return self.defaults.get(key, default)


def _extension_from_mimetype(mimetype):
    extension = mimetypes.guess_extension(mimetype or "")
    if not extension:
        return None
    return extension.strip(".").lower().replace("jpeg", "jpg")


def _mimetype_from_extension(extension):
    extension = (extension or "").lower().strip(".").replace("jpeg", "jpg")
    if extension == "jpg":
        return "image/jpeg"
    if extension:
        return mimetypes.types_map.get("." + extension, "image/" + extension)
    return None


def _normalize_format_metadata(layer, default_mimetype=None):
    """Fill matching ``ext``/``mimetype`` fields without overwriting authors."""

    if "mimetype" in layer and "ext" not in layer:
        extension = _extension_from_mimetype(layer["mimetype"])
        if extension:
            layer["ext"] = extension
    if "ext" in layer and "mimetype" not in layer:
        mimetype = _mimetype_from_extension(layer["ext"])
        if mimetype:
            layer["mimetype"] = mimetype
    if "ext" not in layer and "mimetype" not in layer and default_mimetype:
        layer["mimetype"] = default_mimetype
        extension = _extension_from_mimetype(default_mimetype)
        if extension:
            layer["ext"] = extension


def _normalize_fetch_metadata(layer):
    """Resolve tiny string fetcher aliases used by docs and old configs."""

    fetch = layer.get("fetch")
    if not isinstance(fetch, str):
        return

    from twms import fetchers

    fetchers_by_name = {
        "tile": fetchers.Tile,
        "tms": fetchers.Tile,
        "wms": fetchers.WMS,
    }
    try:
        layer["fetch"] = fetchers_by_name[fetch.lower()]
    except KeyError:
        raise ValueError("Unknown fetcher alias: %s" % fetch)


def normalize_layer_metadata(module):
    """Normalize metadata on a loaded config module in place."""

    default_mimetype = getattr(module, "default_format", None)
    layer_defaults = getattr(module, "layer_defaults", None)
    if isinstance(layer_defaults, dict):
        _normalize_format_metadata(layer_defaults, default_mimetype)
        _normalize_fetch_metadata(layer_defaults)
    for name, layer in list(getattr(module, "layers", {}).items()):
        _normalize_format_metadata(layer, default_mimetype)
        _normalize_fetch_metadata(layer)
        if isinstance(layer_defaults, dict):
            module.layers[name] = LayerConfig(layer_defaults, layer)


def load_config(path):
    """Load a TWMS Python config file and publish it as ``config``.

    Many legacy modules still import ``config`` directly, so the loaded module
    must be registered under both the package and historical top-level names.
    """

    loader = importlib.machinery.SourceFileLoader("twms.config", path)
    spec = importlib.util.spec_from_loader("twms.config", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["twms.config"] = module
    sys.modules["config"] = module
    loader.exec_module(module)
    normalize_layer_metadata(module)
    return module


def load_default_config():
    """Load the first existing config from system, package, then cwd paths."""

    if "config" in sys.modules:
        return sys.modules["config"]

    package_dir = os.path.dirname(__file__)
    paths = [
        "/etc/twms/twms.conf",
        os.path.join(package_dir, "twms.conf"),
        os.path.join(os.path.realpath(sys.path[0]), "twms.conf"),
    ]
    for path in paths:
        if os.path.exists(path):
            return load_config(path)
    return load_config(paths[-1])
