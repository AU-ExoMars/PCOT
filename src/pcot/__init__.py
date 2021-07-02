import importlib
import importlib.resources
import os
import sys
import time

import pcot.macros as macros
import pcot.ui as ui
import pcot.xform as xform
import pcot.xforms
from pcot.config import getUserName, addMainWindowHook, addExprFuncHook
from pcot.utils import archive
from pcot.xforms import *

__version__ = importlib.resources.read_text(pcot, 'VERSION.txt')


##### Plugin handling

# plugin dirs are colon separated, stored in Locations/plugins
pluginDirs = [os.path.expanduser(x) for x in pcot.config.locations.get('pluginpath').split(':')]

# Load any plugins by recursively walking the plugin directories and importing .py files.
for d in pluginDirs:
    for root, dirs, files in os.walk(d):
        for filename in files:
            base, ext = os.path.splitext(filename)
            if ext == '.py':
                path = os.path.join(root, filename)
                print("Loading plugin :", path)
                spec = importlib.util.spec_from_file_location(base, path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[base] = module
                spec.loader.exec_module(module)
