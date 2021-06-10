import time
from typing import Dict

import pcot.config
from pcot.inputs.inp import InputManager
from pcot.macros import XFormMacro
from pcot.utils import archive
from pcot.xform import XFormGraph


class Document:
    """This class contains the main graph, inputs and macros for a PCOT document"""

    graph: XFormGraph
    macros: Dict[str, XFormMacro]
    inputMgr: InputManager

    def __init__(self, fileName=None):
        """Create a new document, and (optionally) load a file into it"""
        self.graph = XFormGraph(False)  # false - is not a macro
        if fileName is not None:
            self.load(fileName)
        else:
            self.graph.create("input 0")

    ## create a dictionary of everything in the app we need to save: global settings,
    # the graph, macros etc.
    def serialise(self):
        d = {'SETTINGS': {'cap': self.graph.captionType},
             'INFO': {'author': pcot.config.getUserName(),
                      'date': time.time()},
             'GRAPH': self.graph.serialise(),
             'INPUTS': self.graph.inputMgr.serialise(),
             'MACROS': XFormMacro.serialiseAll()
             }
        return d

    ## deserialise everything from the given top-level dictionary into an existing graph;
    # also deserialises the macros (which are global to all graphs).
    # Deserialising the inputs is optional : we don't do it if we are loading templates
    # or if there is no INPUTS entry in the file, or there's no input manager (shouldn't
    # happen unless we're doing something weird like loading a macro prototype graph)
    def deserialise(self, d, deserialiseInputs=True):
        # deserialise macros before graph!
        if 'MACROS' in d:
            XFormMacro.deserialiseAll(d['MACROS'])
        self.graph.deserialise(d['GRAPH'], True)  # True to delete existing nodes first

        if 'INPUTS' in d and deserialiseInputs and self.graph.inputMgr is not None:
            self.graph.inputMgr.deserialise(d['INPUTS'])

        settings = d['SETTINGS']
        self.graph.captionType = settings['cap']

    def save(self, fname):
        # note that the archive mechanism deals with numpy array saving and also
        # saves to a temp file before moving when it's all OK at the end.
        with archive.FileArchive(fname, 'w') as arc:
            arc.writeJson("JSON", self.serialise())
            pcot.config.addRecent(fname)

    def load(self, fname):
        """Load data into this document - is used in ctor, can also be used on existing document.
        Also adds to the recent files list.
        May throw exceptions, typically FileNotFoundError"""
        with archive.FileArchive(fname) as arc:
            dd = arc.readJson("JSON")
            self.deserialise(dd)
            pcot.config.addRecent(fname)



