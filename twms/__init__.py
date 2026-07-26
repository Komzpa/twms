# -*- coding: utf-8 -*-

import os
import sys

package_dir = os.path.dirname(__file__)
if package_dir not in sys.path:
    sys.path.append(package_dir)

from .config_loader import load_default_config
from .version import __version__


load_default_config()


def __getattr__(name):
    if name in {"getimg", "tile_image", "twms_main"}:
        from . import twms as twms_module

        return getattr(twms_module, name)
    raise AttributeError(name)


__all__ = [
    "__version__",
    "twms",
    "bbox",
    "canvas",
    "correctify",
    "drawing",
    "image_compat",
    "josm",
    "projections",
    "reproject",
    "wmts",
]
