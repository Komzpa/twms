PREFIX ?= /usr
prefix ?= $(PREFIX)

ifeq ($(prefix),/usr)
sysconfdir ?= /etc
localstatedir ?= /var
else
sysconfdir ?= $(prefix)/etc
localstatedir ?= $(prefix)/var
endif

exec_prefix ?= $(prefix)
bindir ?= $(exec_prefix)/bin
datarootdir ?= $(prefix)/share
docdir ?= $(datarootdir)/doc/$(PACKAGE)
mandir ?= $(datarootdir)/man
libdir ?= $(exec_prefix)/lib

INSTALL ?= install
INSTALL_DATA = $(INSTALL) -m 644
INSTALL_PROGRAM = $(INSTALL) -m 755
MKDIR = mkdir -m 755

SYMLINK ?= cp -as

ETCDIR = $(sysconfdir)/$(PACKAGE)
DATADIR = $(datarootdir)/$(PACKAGE)
PYTHONDIR ?= $(datarootdir)/pyshared

PYTHON ?= python
PYTHONLIBDIR ?= $(shell $(PYTHON) -c "import distutils.sysconfig; print distutils.sysconfig.get_python_lib()")

build: user-build

user-build user-install::

install: install-dirs install-bin install-config install-doc install-man install-data install-python user-install

install-dirs:
	for item in $(DIRS); do \
		$(INSTALL) -d $(DESTDIR)$$item; \
	done

install-bin:
	[ -z "$(BIN)" ] || $(INSTALL) -d $(DESTDIR)$(bindir)
	for item in $(BIN); do \
		$(INSTALL_PROGRAM) -D $$item $(DESTDIR)$(bindir)/$$(basename $$item); \
	done

install-config:
	[ -z "$(ETC)" ] || $(INSTALL) -d $(DESTDIR)$(ETCDIR)
	for item in $(ETC); do \
		$(INSTALL_DATA) -D $$item $(DESTDIR)$(ETCDIR)/$$(basename $$item); \
	done

install-doc:
	[ -z "$(DOC)" ] || $(INSTALL) -d $(DESTDIR)$(docdir)
	for item in $(DOC); do \
		$(INSTALL_DATA) -D $$item $(DESTDIR)$(docdir)/$$(basename $$item); \
	done

install-man:
	[ -z "$(MANPAGES)" ] || $(INSTALL) -d $(DESTDIR)$(mandir)
	for item in $(MANPAGES); do \
		$(INSTALL_DATA) -D $$item $(DESTDIR)$(mandir)/man$${item##*.}/$$item; \
	done

install-data:
	[ -z "$(DATA)" ] || $(INSTALL) -d $(DESTDIR)$(DATADIR)
	for item in $(DATA); do \
		$(INSTALL_DATA) -D $$item $(DESTDIR)$(DATADIR)/$$item; \
	done

install-python:
	[ -z "$(PYTHONSCRIPTS)" ] || $(INSTALL) -d $(DESTDIR)$(PYTHONDIR)
	[ -z "$(PYTHONLIBDIR)" ] || $(MKDIR) -p $(DESTDIR)$(PYTHONLIBDIR)
	for pkg in $(PYTHONPKGS); do \
		$(MKDIR) -p $(DESTDIR)$(PYTHONDIR)/$$pkg; \
		for item in $$(find $$pkg/*); do \
			$(INSTALL_DATA) -D $$item $(DESTDIR)$(PYTHONDIR)/$$item; \
		done; echo $(PYTHONLIBDIR); \
		[ -z "$(PYTHONLIBDIR)" ] || $(SYMLINK) $(PYTHONDIR)/$$pkg $(DESTDIR)$(PYTHONLIBDIR); \
	done

.PHONY: build user-build install install-dirs install-bin install-config install-doc install-man install-data install-python user-install
