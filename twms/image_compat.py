# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.


def resampling_lanczos(Image):
    """Return the best Pillow downsampling filter across old and new Pillow."""
    if hasattr(Image, "Resampling"):
        return Image.Resampling.LANCZOS
    return Image.ANTIALIAS
