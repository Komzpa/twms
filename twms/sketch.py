# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

from bbox import *

string = "abcdefghijklmnopqrstuvwxyz012345ABCDEFGHIJKLMNOPQRSTUVWXYZ6789{}"


def decode(bbox, sketch):
    version, sketch = sketch.split(";", 1)


def encode_point(bbox, point, length, length_out=None):
    if not length_out:
        length_out = length
    code = "."
    if not point_is_in(bbox, point):
        bbox = (-180, -90, 180, 90)
        code += "@"
        length = length_out - 1
    lon, lat = point
    lon = (lon - bbox[0]) / (bbox[2] - bbox[0])  # normalizing points to bbox
    lat = (lat - bbox[1]) / (bbox[3] - bbox[1])
    lats, lons = [], []

    for i in range(0, length):
        latt = int(lat * 8)
        lont = int(lon * 8)
        lat = lat * 8 - int(lat * 8)
        lon = lon * 8 - int(lon * 8)
        code += string[lont * 8 + latt]
    return code


def decode_point(bbox, code):
    lat, lon = (0, 0)
    if code[0] == ".":
        code = code[1:]
        if code[0] == "@":
            code = code[1:]
            bbox = (-180, -90, 180, 90)
        c = ""
        code = " " + code  # reverse
        for a in range(0, len(code) - 1):
            c += code[-1]
            code = code[:-1]

        code = c

        for t in code:
            z = string.find(t)
            lont = int(z / 8.0)
            latt = (z / 8.0 - int(z / 8.0)) * 8
            lat += latt
            lat /= 8.0
            lon += lont
            lon /= 8.0
        lat = lat * (bbox[3] - bbox[1]) + bbox[1]
        lon = lon * (bbox[2] - bbox[0]) + bbox[0]
        return lon, lat


# Window.alert(code_point((0,0,0,0), 53.11, 27.3434))
# print(decode_point((0,0,0,0), ".@aaa"))
