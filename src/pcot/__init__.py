import configparser,os,io
import getpass
import importlib
import sys
import time
import traceback

from pkg_resources import resource_string as resource_bytes
import pcot.macros as macros
import pcot.ui as ui
import pcot.xform as xform

from pcot.utils import archive

# import all transform types (see the __init__.py there)
# ACTUALLY REQUIRED despite what the IDE says! DO NOT
# REMOVE THESE LINES!

import pcot.xforms
from pcot.xforms import *


def getAssetAsFile(fn):
    s = resource_bytes('pcot.assets',fn).decode('utf-8')
    return io.StringIO(s)


## return the current username, whichis either obtained from the OS
# or from the PCOT_USER environment variable

def getUserName():
    if 'PCOT_USER' in os.environ:
        return os.environ['PCOT_USER']
    else:
        return getpass.getuser()


## create a dictionary of everything in the app we need to save: global settings,
# the graph, macros etc.
def serialise(graph):
    d = {'SETTINGS': {'cap': graph.captionType},
         'INFO': {'author': getUserName(),
                  'date': time.time()},
         'GRAPH': graph.serialise(),
         'INPUTS': graph.inputMgr.serialise(),
         'MACROS': macros.XFormMacro.serialiseAll()}
    # now we also have to serialise the macros
    return d


## deserialise everything from the given top-level dictionary into an existing graph;
# also deserialises the macros (which are global to all graphs).
# Deserialising the inputs is optional : we don't do it if we are loading templates
# or if there is no INPUTS entry in the file, or there's no input manager (shouldn't
# happen unless we're doing something weird like loading a macro prototype graph)
def deserialise(d, graph, deserialiseInputs=True):
    # deserialise macros before graph!
    if 'MACROS' in d:
        macros.XFormMacro.deserialiseAll(d['MACROS'])
    graph.deserialise(d['GRAPH'], True)  # True to delete existing nodes first

    if 'INPUTS' in d and deserialiseInputs and graph.inputMgr is not None:
        graph.inputMgr.deserialise(d['INPUTS'])

    settings = d['SETTINGS']
    graph.captionType = settings['cap']


def save(fname, graph):
    # note that the archive mechanism deals with numpy array saving and also
    # saves to a temp file before moving when it's all OK at the end.
    with archive.FileArchive(fname, 'w') as arc:
        arc.writeJson("JSON", serialise(graph))


## Load a PCOT graph (an XFormGraph) from a .pcot file, either into an existing graph or
# a new one.

def load(fname, graph=None):
    if graph is None:
        graph = xform.XFormGraph(False)
    with archive.FileArchive(fname) as arc:
        d = arc.readJson("JSON")
    deserialise(d, graph)
    return graph


config = None

config = configparser.ConfigParser()
config.read_file(getAssetAsFile('defaults.ini'))
config.read(['site.cfg', os.path.expanduser('~/.pcot.ini')], encoding='utf_8')

# A list of functions for adding stuff to the main window. Each takes a MainUI
mainWindowInitHooks = []


##### Plugin handling

# plugin dirs are colon separated, stored in Locations/plugins
pluginDirs = [os.path.expanduser(x) for x in config.get('Locations', 'pluginpath').split(':')]

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




