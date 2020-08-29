# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms specified in COPYING.

from twms import twms


if __name__ != "__main__":
    try:
        from mod_python import apache, util
        import datetime
    except ImportError:
        pass


def handler(req):
    """
    A handler for mod_python.
    """
    data = util.FieldStorage(req)
    data = dict((k.lower(), data[k]) for k in iter(data))
    resp, ctype, content = twms.twms_main(data)
    req.content_type = ctype
    req.write(content)
    return resp
