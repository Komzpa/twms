include Makefile.mk

PACKAGE = twms
CACHEDIR = $(localstatedir)/cache/$(PACKAGE)

MANPAGES = twms.1
BIN = twms.py
DOC = README
ETC = twms/twms.conf
DATA = tools/* irs_nxt.jpg yahoo_nxt.jpg yandex_nxt.jpg
DIRS = $(CACHEDIR)/traces $(CACHEDIR)/tiles
PYTHON = twms/*

user-install::
	echo sed -i \
		-e 's,/var/cache/twms/,$(CACHEDIR),g' \
		-e 's,/usr/share/twms/,$(DATADIR),g' \
		$(DESTDIR)$(ETCDIR)/twms.conf
	mv $(DESTDIR)$(bindir)/twms.py $(DESTDIR)$(bindir)/twms

