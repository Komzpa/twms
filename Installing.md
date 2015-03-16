tWMS depends on:
  * python
  * python-webpy >= 0.3
  * python-pyproj ([Pyrex generated python interface  to PROJ.4 library](http://code.google.com/p/pyproj/downloads/list))
  * python-imaging

BEWARE: config file is only an example. You may need to adjust it to your own needs.

## Getting source code ##

In case you need source code, you may:

  * get it from mercurial repo:
```
hg clone https://twms.googlecode.com/hg/ twms 
```
  * get released tarball from Downloads page: http://code.google.com/p/twms/downloads/list

# Linux #

## Debian package ##

twms is available in unstable debian distribution. So, just:
```
aptitude install twms
```

and don't forget to set RUN="yes" in /etc/default/twms.

## standalone web.py run ##

To run tWMS in web.py standalone mode, make sure to [configure](Config.md) it and install all dependencies. Afterwards, start it as
```
python twms.py
```

tWMS will serve as http://localhost:8080/.


## josm external renderer ##
tWMS can be used inside [josm](http://josm.openstreetmap.de/) without starting any port-requiring services.

To set up in josm, make sure you install twms and all its dependencies.
  1. chmod +x twms.py
  1. in josm: Edit > Preferences > WMS > Downloader: set to `path/to/twms.py josm {0}`
  1. now you can use WMS URLs like `html:http://twms/?layers=yhsat&`; they will be processed by tWMS


## apache + mod\_python ##

This method is not supported now. Patches welcome, but better to migrate to mod\_wsgi.

Support was dropped due to unability to make a simple RAM-cache with mod\_python.


Create a vhost file similar to:

```
<VirtualHost *>
  ServerAdmin youradmin@yourmachine
  ServerName wms.yourdomain.yourtld
  DocumentRoot /srv/www/htdocs/twms
 
  <Directory /srv/www/htdocs/twms/>
 
    SetHandler python-program
    AddHandler python-program .py
    PythonHandler index
    Order allow,deny
    Allow from all
  </Directory>
  ErrorLog /var/log/apache2/twms-error.log
  LogLevel warn
  CustomLog /var/log/apache2/twms-access.log combined
</VirtualHost>
```

Download all twms files from http://twms.googlecode.com/hg/ to
your htdocs/twms folder.

Cookbook as above; adjust Config paths to your needs.


## apache + mod\_wsgi ##


```
WSGIPythonPath /var/www/latlon/wms/:/var/www/latlon/wms/twms/
WSGIDaemonProcess twmsd user=www-data group=www-data display-name=(wsgi:twms) python-path=/var/www/latlon/wms/

<VirtualHost *>
        ServerAdmin me@komzpa.net
        ServerName wms.play.latlon.org
        DocumentRoot /var/www/latlon/wms
        WSGIScriptAlias / /var/www/latlon/wms/twms.py
        WSGIProcessGroup twmsd
        AddType text/html .py
<Directory /var/www/latlon/wms/>
    Order deny,allow
    Allow from all
</Directory>
        ErrorLog /var/log/apache2/error.log
        LogLevel warn
        CustomLog /var/log/apache2/access.log combined
        ServerSignature On

</VirtualHost>

```

# Windows #

## py2exe win32 compiled fork ##

There is tWMS fork, compiled as windows executable by kolen. You just need to download  and run index.exe from that archive.

Using: Use  http://localhost:8080/?layers=...& as WMS address in JOSM. Available layers include [irs](http://wiki.openstreetmap.org/wiki/WikiProject_Russia/kosmosnimki) (http://localhost:8080/?layers=irs&) for IRS mosaic and yhsat (http://localhost:8080/?layers=yhsat&) for Yahoo Satellite Imagery. Config file is compiled into tWMS executable, you need to try other ways if you need to edit it.

## apache + mod\_python ##

Depends on:

  * apache
  * python 2.5 (!!! there is no mod\_python for python 2.6 for windows)
  * mod\_python for python 2.5
  * PIL
  * pyproj

These versions were used while writing manual:

  * apache\_2.2.14-win32-x86-openssl-0.9.8k.msi
  * python-2.5.4.msi
  * mod\_python-3.3.1.win32-py2.5-Apache2.2.exe
  * PIL-1.1.6.win32-py2.5.exe
  * pyproj-1.8.5.win32-py2.5.exe

Everything was installed with default settings.

Edit file C:\Program Files\Apache Software Foundation\Apache2.2\conf\httpd.conf.
Find rows starting with LoadModule. Add after the last of them:

```
 LoadModule python_module modules/mod_python.so
```

Write to the end of this file:
```
 <Directory "C:/Program Files/Apache Software Foundation/Apache2.2/htdocs">
    DirectoryIndex index.py
    AddHandler mod_python .py
    PythonHandler index
    PythonDebug on
 </Directory>
```

Download all twms files from http://twms.googlecode.com/hg/ to
C:\Program Files\Apache Software Foundation\Apache2.2\htdocs.

Then edit config.py tWMS Config. Change all paths in the top to correspond to your setup at least.

Restart apache from Apache Monitor, which can be launched from system tray.

To check if it works correctly, open in browser:

http://localhost/?layers=irs&bbox=38.2645676,56.1453162,39.4603353,56.8057105&srs=EPSG:4326&width=500&height=499