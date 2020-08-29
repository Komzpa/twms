# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

try:
    from PIL import Image
except ImportError:
    import Image

import projections
import sys


def reproject(image, bbox, srs_from, srs_to):
    out = image.copy()
    op = out.load()
    il = image.load()
    bbox_from = projections.from4326(bbox, srs_from)
    bbox_to = projections.from4326(bbox, srs_to)
    width, height = image.size

    for x in range(0, width):
        for y in range(0, height):
            dx = ((1.0 * x / width) * (bbox_to[2] - bbox_to[0])) + bbox_to[0]
            dy = ((1.0 * y / height) * (bbox_to[3] - bbox_to[1])) + bbox_to[1]
            # print(x, dx, y, dy, file=sys.stderr)
            dx, dy = tuple(projections.transform([dx, dy], srs_to, srs_from))

            dx = width * (dx - bbox_from[0]) / (bbox_from[2] - bbox_from[0])
            dy = height * (dy - bbox_from[1]) / (bbox_from[3] - bbox_from[1])
            op[x, y] = il[int(dx), int(dy)]

            # sys.stderr.flush()
    return out
