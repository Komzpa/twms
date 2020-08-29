# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

import sys
import projections


def point_is_in(bbox, point):
    """
    Check whether EPSG:4326 point is in bbox
    """
    # bbox = normalize(bbox)[0]

    return (
        point[0] >= bbox[0]
        and point[0] <= bbox[2]
        and point[1] >= bbox[1]
        and point[1] <= bbox[3]
    )


def bbox_is_in(bbox_outer, bbox_to_check, fully=True):
    """
    Check whether EPSG:4326 bbox is inside outer
    """
    bo = normalize(bbox_outer)[0]
    bc = normalize(bbox_to_check)[0]
    if fully:
        return (bo[0] <= bc[0] and bo[2] >= bc[2]) and (
            bo[1] <= bc[1] and bo[3] >= bc[3]
        )
    else:
        if bo[0] > bc[0]:
            bo, bc = bc, bo
        if bc[0] <= bo[2]:
            if bo[1] > bc[1]:
                bo, bc = bc, bo
            return bc[1] <= bo[3]
        return False

        return (
            ((bo[0] <= bc[0] and bo[2] >= bc[0]) or (bo[0] <= bc[2] and bo[2] >= bc[2]))
            and (
                (bo[1] <= bc[1] and bo[3] >= bc[1])
                or (bo[1] <= bc[3] and bo[3] >= bc[3])
            )
            or (
                (bc[0] <= bo[0] and bc[2] >= bo[0])
                or (bc[0] <= bo[2] and bc[2] >= bo[2])
            )
            and (
                (bc[1] <= bo[1] and bc[3] >= bo[1])
                or (bc[1] <= bo[3] and bc[3] >= bo[3])
            )
        )


def add(b1, b2):
    """
    Return bbox containing two bboxes.
    """
    return (min(b1[0], b2[0]), min(b1[1], b2[1]), max(b1[2], b2[2]), max(b1[3], b2[3]))


def expand_to_point(b1, p1):
    """
    Expand bbox b1 to contain p1: [(x,y),(x,y)]
    """
    for p in p1:
        b1 = add(b1, (p[0], p[1], p[0], p[1]))
    return b1


def normalize(bbox):
    """
    Normalise EPSG:4326 bbox order. Returns normalized bbox, and whether it was flipped on horizontal axis.
    """

    flip_h = False
    bbox = list(bbox)
    while bbox[0] < -180.0:
        bbox[0] += 360.0
        bbox[2] += 360.0
    if bbox[0] > bbox[2]:
        bbox = (bbox[0], bbox[1], bbox[2] + 360, bbox[3])
        # bbox = (bbox[2],bbox[1],bbox[0],bbox[3])
    if bbox[1] > bbox[3]:
        flip_h = True
        bbox = (bbox[0], bbox[3], bbox[2], bbox[1])

    return bbox, flip_h


def zoom_for_bbox(bbox, size, layer, min_zoom=1, max_zoom=18, max_size=(10000, 10000)):
    """
    Calculate a best-fit zoom level
    """

    h, w = size
    for i in range(min_zoom, max_zoom):
        cx1, cy1, cx2, cy2 = projections.tile_by_bbox(bbox, i, layer["proj"])
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
