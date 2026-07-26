# -*- coding: utf-8 -*-

import importlib.machinery
import importlib.util
import os
import sys


def load_config(path):
    loader = importlib.machinery.SourceFileLoader("twms.config", path)
    spec = importlib.util.spec_from_loader("twms.config", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["twms.config"] = module
    sys.modules["config"] = module
    loader.exec_module(module)
    return module


def load_default_config():
    if "config" in sys.modules:
        return sys.modules["config"]

    package_dir = os.path.dirname(__file__)
    paths = [
        "/etc/twms/twms.conf",
        os.path.join(package_dir, "twms.conf"),
        os.path.join(os.path.realpath(sys.path[0]), "twms.conf"),
    ]
    for path in paths:
        if os.path.exists(path):
            return load_config(path)
    return load_config(paths[-1])
