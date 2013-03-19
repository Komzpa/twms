include Makefile.mk

PACKAGE = twms
CACHEDIR = $(localstatedir)/cache/$(PACKAGE)

MANPAGES = twms.1
BIN = twms.py
DOC = README.md
ETC = twms/twms.conf
DATA = tools/* irs_nxt.jpg yahoo_nxt.jpg yandex_nxt.jpg
DIRS = $(CACHEDIR)/traces $(CACHEDIR)/tiles
PYTHON = twms/*

user-install::
	sed -i \
		-e 's,/etc/twms,$(ETCDIR),g' \
		-e 's,/var/cache/twms,$(CACHEDIR),g' \
		-e 's,/usr/share/twms,$(DATADIR),g' \
		-e 's,/usr/share/pyshared,$(PYTHONDIR),g' \
		$(DESTDIR)$(ETCDIR)/twms.conf \
		$(DESTDIR)$(PYTHONDIR)/twms/twms.conf \
		$(DESTDIR)$(PYTHONDIR)/twms/twms.py
	mv $(DESTDIR)$(bindir)/twms.py $(DESTDIR)$(bindir)/twms

