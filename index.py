# -*- coding: utf-8 -*-
#    This file is part of tWMS.

#   tWMS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.

#   tWMS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with tWMS.  If not, see <http://www.gnu.org/licenses/>.


import twms


if __name__ != '__main__':
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
    data = dict((k.lower(), v) for k, v in data.iteritems())
    resp, ctype, content = twms.twms_main(data)
    req.content_type = ctype
    req.write(content)
    return resp