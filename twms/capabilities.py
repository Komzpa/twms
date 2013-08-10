# -*- coding: utf-8 -*-
#    This file is part of twms.

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://www.wtfpl.net/ for more details.

import config
import projections

def get(version, ref):
   content_type = "text/xml"
   
   if version == "1.0.0":
      req = """
<?xml version="1.0" standalone="no"?>
<!-- The DTD (Document Type Definition) given here must correspond to the version number declared in the WMT_MS_Capabilities element below. -->
<!DOCTYPE WMT_MS_Capabilities SYSTEM "http://www2.demis.nl/WMS/capabilities_1_0_0.dtd"
<!ENTITY % KnownFormats " SGI | GIF | JPEG | PNG | WebCGM | SVG | GML.1
 | WMS_XML | MIME | INIMAGE | PPM | BLANK " >
<!ELEMENT SGI EMPTY> <!-- Silicon Graphics RGB Format -->

 <!-- other vendor-specific elements defined here -->
 <!ELEMENT VendorSpecificCapabilities (YMD)>
 <!ELEMENT YMD (Title, Abstract)>
 <!ATTLIST YMD required (0 | 1) "0">

 ]>

<!-- end of DOCTYPE declaration -->
<!-- The version number listed in the WMT_MS_Capabilities element here must correspond to the DTD declared above.  See the WMT specification document for how to respond when a client requests a version number not implemented by the server. -->
<WMT_MS_Capabilities version=\"""" +str(version)+ """">
        <Service>
                <!-- The WMT-defined name for this type of service -->
                <Name>GetMap</Name>
                <!-- Human-readable title for pick lists -->
                <Title>""" + config.wms_name + """</Title>
                <!-- Narrative description providing additional information -->

                <Abstract>None</Abstract>
                <Keywords></Keywords>
                <!-- Top-level address of service or service provider.  See also onlineResource attributes of <DCPType> children. -->
                <OnlineResource>"""+ ref +"""</OnlineResource>
                <!-- Fees or access constraints imposed. -->
                <Fees>none</Fees>
                <AccessConstraints>none</AccessConstraints>

        </Service>
        <Capability>
                <Request>
                        <Map>
                                <Format>
                                        <GIF/>
                                        <JPEG/>
                                        <PNG/>
                                        <BMP/>

                                </Format>
                                <DCPType>
                                        <HTTP>
                                                <!-- The URL here for HTTP GET requests includes only the prefix before the query string.-->
                                                <Get onlineResource=\"""" + ref + """?"/>
                                        </HTTP>
                                </DCPType>
                        </Map>
                        <Capabilities>

                                <Format>
                                        <WMS_XML/>
                                </Format>
                                <DCPType>
                                        <HTTP>
                                                <!-- The URL here for HTTP GET requests includes only the prefix before the query string.-->
                                                <Get onlineResource=\"""" + ref + """?"/>
                                        </HTTP>
                                </DCPType>

                        </Capabilities>
                </Request>
                <Exception>
                        <Format>
                                <WMS_XML/>
                                <INIMAGE/>
                                <BLANK/>

                        </Format>
                </Exception>
                <Layer>
                        <Title>""" + config.wms_name + """</Title>
                        <Abstract/>"""
      pset = set(projections.projs.keys())
      pset = pset.union(set(projections.proj_alias.keys()))
      for proj in pset:
           req += "<SRS>%s</SRS>" % proj
      req += """<LatLonBoundingBox minx="-180" miny="-85.0511287798" maxx="180" maxy="85.0511287798"/>
                        <BoundingBox SRS="EPSG:4326" minx="-184" miny="85.0511287798" maxx="180" maxy="85.0511287798"/>
"""
      
      lala = """<Layer queryable="1">
                                <Name>%s</Name>
                                <Title>%s</Title>
                                <BoundingBox SRS="EPSG:4326" minx="%s" miny="%s" maxx="%s" maxy="%s"/>
                                <ScaleHint min="0" max="124000"/>
                        </Layer>"""
      for i in config.layers.keys():
          b = config.layers[i].get("bbox", config.default_bbox)
          req += lala%(i,config.layers[i]["name"],b[0],b[1],b[2],b[3])

      req += """          </Layer>
        </Capability>
</WMT_MS_Capabilities>"""





   else:
      content_type = "application/vnd.ogc.wms_xml"
      req = """<?xml version="1.0"?>
<!DOCTYPE WMT_MS_Capabilities SYSTEM "http://www2.demis.nl/WMS/capabilities_1_1_1.dtd" [
 <!-- Vendor-specific elements are defined here if needed. -->
 <!-- If not needed, just leave this EMPTY declaration.  Do not
  delete the declaration entirely. -->
 <!ELEMENT VendorSpecificCapabilities EMPTY>
 ]>
<WMT_MS_Capabilities version=\""""+ str(version) +"""">
        <!-- Service Metadata -->
        <Service>
                <!-- The WMT-defined name for this type of service -->
                <Name>twms</Name>
                <!-- Human-readable title for pick lists -->
                <Title>""" + config.wms_name + """</Title>
                <!-- Narrative description providing additional information -->
                <Abstract>None</Abstract>
                <!-- Top-level web address of service or service provider.  See also OnlineResource
  elements under <DCPType>. -->
                <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:type="simple" xlink:href=\"""" + ref+ """"/>
                <!-- Contact information -->
                <ContactInformation>
                        <ContactPersonPrimary>
                                <ContactPerson>"""+config.contact_person["real_name"]+"""</ContactPerson>
                                <ContactOrganization>"""+config.contact_person["organization"]+"""</ContactOrganization>
                        </ContactPersonPrimary>
                        <ContactElectronicMailAddress>"""+config.contact_person["mail"]+"""</ContactElectronicMailAddress>
                </ContactInformation>
                <!-- Fees or access constraints imposed. -->
                <Fees>none</Fees>
                <AccessConstraints>none</AccessConstraints>
        </Service>
        <Capability>
                <Request>
                        <GetCapabilities>
                                <Format>application/vnd.ogc.wms_xml</Format>
                                <DCPType>
                                        <HTTP>
                                                <Get>
                                                        <!-- The URL here for invoking GetCapabilities using HTTP GET
            is only a prefix to which a query string is appended. -->
                                                        <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:type="simple" xlink:href=\"""" + ref + """?"/>
                                                </Get>
                                        </HTTP>
                                </DCPType>
                        </GetCapabilities>
                        <GetMap>
                                <Format>image/png</Format>
                                <Format>image/jpeg</Format>
                                <Format>image/gif</Format>
                                <Format>image/bmp</Format>
                                <DCPType>
                                        <HTTP>
                                                <Get>
                                                        <!-- The URL here for invoking GetCapabilities using HTTP GET
            is only a prefix to which a query string is appended. -->
                                                        <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:type="simple" xlink:href=\"""" + ref + """?"/>
                                                </Get>
                                        </HTTP>
                                </DCPType>
                        </GetMap>
                </Request>
                <Exception>
                        <Format>application/vnd.ogc.se_inimage</Format>
                        <Format>application/vnd.ogc.se_blank</Format>
                        <Format>application/vnd.ogc.se_xml</Format>
                        <Format>text/xml</Format>
                        <Format>text/plain</Format>
                </Exception>
                <VendorSpecificCapabilities/>
                <Layer>
                        <Title>World Map</Title>"""
      pset = set(projections.projs.keys())
      pset = pset.union(set(projections.proj_alias.keys()))
      for proj in pset:
           req += "<SRS>%s</SRS>" % proj
      req += """
                        <LatLonBoundingBox minx="-180" miny="-85.0511287798" maxx="180" maxy="85.0511287798"/>
                        <BoundingBox SRS="EPSG:4326" minx="-180" miny="-85.0511287798" maxx="180" maxy="85.0511287798"/>
"""
      lala = """
                        <Layer queryable="0" opaque="1">
                                <Name>%s</Name>
                                <Title>%s</Title>
                                <BoundingBox SRS="EPSG:4326" minx="%s" miny="%s" maxx="%s" maxy="%s"/>
                                <ScaleHint min="0" max="124000"/>
                        </Layer>
"""
      for i in config.layers.keys():
          b = config.layers[i].get("bbox", config.default_bbox)
          req += lala%(i,config.layers[i]["name"],b[0],b[1],b[2],b[3])

      req += """          </Layer>
        </Capability>
</WMT_MS_Capabilities>"""

   return content_type, req
