#!/usr/bin/python3

import os
import platform
from glob import glob as abs_glob

from setuptools import find_packages, setup


__platform__ = platform.system()
is_windows = __platform__ in ['Windows']

__name__ = "twms"
__dir__ = os.path.dirname(__file__)


def read(fname):
    return (
        open(os.path.join(__dir__, fname), 'rb')
        .read()
        .decode('utf-8')
    )


def glob(fname):
    return [os.path.relpath(x, __dir__) for x in abs_glob(os.path.join(__dir__, fname))]


def man_path(fname):
    category = fname.rsplit('.', 1)[1]
    return os.path.join('share', 'man', 'man' + category), [fname]

def man_files(pattern):
    return list(map(man_path, glob(pattern)))


def config_files():
    if not is_windows:
        return [(os.path.join('/etc', __name__), [os.path.join('twms', 'twms.conf')])]
    else:
        return []


# monkey patch setuptools to use distutils owner/group functionality
from setuptools.command import sdist


sdist_org = sdist.sdist


class sdist_new(sdist_org):
    def initialize_options(self):
        sdist_org.initialize_options(self)
        self.owner = self.group = 'root'


sdist.sdist = sdist_new

setup(
    name = __name__,
    data_files = [
        (os.path.join('share', 'doc', __name__), ['COPYING']),
        (os.path.join('share', 'doc', __name__), glob('*.md')),
        (os.path.join('share', __name__), glob('*.jpg')),
        (os.path.join('share', __name__, 'tools'), glob(os.path.join('tools', '*.py')))
    ] + man_files('*.1') + config_files(),
)
