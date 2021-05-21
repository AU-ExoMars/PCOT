import importlib
import os
import sys
import time

import pcot.macros as macros
import pcot.ui as ui
import pcot.xform as xform
import pcot.xforms
from pcot.config import getUserName
from pcot.utils import archive
from pcot.xforms import *


# import all transform types (see the __init__.py there)
# ACTUALLY REQUIRED despite what the IDE says! DO NOT
# REMOVE THESE LINES!


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
        pcot.config.addRecent(fname)


## Load a PCOT graph (an XFormGraph) from a .pcot file, either into an existing graph or
# a new one.

def load(fname, graph=None):
    if graph is None:
        graph = xform.XFormGraph(False)
    with archive.FileArchive(fname) as arc:
        dd = arc.readJson("JSON")
        deserialise(dd, graph)
        pcot.config.addRecent(fname)
    return graph


# A list of functions for adding stuff to the main window. Each takes a MainUI
mainWindowInitHooks = []

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
