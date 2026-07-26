# Installing and running TWMS

## Dependencies

The base package is intentionally small:

- Python 3.11 or newer
- Pillow
- `web.py` for the preserved legacy WSGI/standalone entry point

Optional extras:

```sh
python -m pip install -e '.[proj]'
python -m pip install -e '.[cairo]'
```

- `twms[proj]` enables pyproj-backed transformations for configured
  non-core projections.
- `twms[cairo]` enables Cairo-backed vector rendering for deployments that used
  the older Cairo/Pango rendering path.

## From a checkout

```sh
python -m pip install -e .
twms 8080
```

The default server uses the Python standard library and listens on
`http://127.0.0.1:8080/`.

The legacy `web.py` server remains available:

```sh
twms-webpy
```

That path is kept for old WSGI setups and small Windows/JOSM proxy bundles that
depended on `web.py`.

## Debian

TWMS has historically been packaged for Debian. If your distribution carries the
package, prefer the package manager and then adjust `/etc/twms/twms.conf`:

```sh
sudo apt install twms
```

Older Debian packages used `/etc/default/twms` with `RUN="yes"` for service
startup. Check the packaging shipped by your distribution, because service
management may differ between releases.

## WSGI

The WSGI application is still importable as `twms.daemon.application`.

A minimal mod_wsgi deployment looks like:

```apache
WSGIDaemonProcess twms user=www-data group=www-data
WSGIProcessGroup twms
WSGIScriptAlias / /path/to/twms/index.py

<Directory /path/to/twms>
    Require all granted
</Directory>
```

The old Google Code wiki also documented `mod_python`; that stack is obsolete
and is not recommended for new deployments.

## Windows and JOSM proxy use

GitHub Actions builds Windows executable artifacts from the current branch:

- `twms.exe` for the stdlib server
- `twms-webpy.exe` for the preserved `web.py` entry point

Optional launcher templates are packaged under `share/twms/contrib/`:

- `twms.bat`
- `twms.desktop`

For JOSM, run TWMS locally and add a TMS imagery entry such as:

```text
tms:http://127.0.0.1:8080/osm/{zoom}/{x}/{y}.png
```

When a layer needs TWMS-specific parameters such as filters, use the legacy
`GetTile` style:

```text
tms:http://127.0.0.1:8080/?request=GetTile&layers=osm&z={zoom}&x={x}&y={y}&format=png
```

TWMS also publishes a JOSM imagery list:

```text
http://127.0.0.1:8080/josm/imagery.xml
```
