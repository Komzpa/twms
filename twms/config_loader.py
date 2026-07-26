# -*- coding: utf-8 -*-

import importlib.machinery
import importlib.util
import mimetypes
import os
import sys


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


def normalize_layer_metadata(module):
    default_mimetype = getattr(module, "default_format", None)
    for layer in getattr(module, "layers", {}).values():
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


def load_config(path):
    loader = importlib.machinery.SourceFileLoader("twms.config", path)
    spec = importlib.util.spec_from_loader("twms.config", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["twms.config"] = module
    sys.modules["config"] = module
    loader.exec_module(module)
    normalize_layer_metadata(module)
    return module


def load_default_config():
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
