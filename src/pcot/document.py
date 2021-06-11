import time
from typing import Dict

import pcot.config
from pcot import inputs
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
        self.inputMgr = InputManager(self)
        self.graph = XFormGraph(self, False)  # false - is not a macro
        self.macros = {}

        if fileName is not None:
            self.load(fileName)
        else:
            self.graph.create("input 0")

    ## create a dictionary of everything in the app we need to save: global settings,
    # the graph, macros etc.
    def serialise(self):
        macros = {}
        for k, v in self.macros:
            macros[k] = v.graph.serialise()

        d = {'SETTINGS': {'cap': self.graph.captionType},
             'INFO': {'author': pcot.config.getUserName(),
                      'date': time.time()},
             'GRAPH': self.graph.serialise(),
             'INPUTS': self.inputMgr.serialise(),
             'MACROS': macros
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
            for k, v in d['MACROS'].items():
                p = XFormMacro(self, k) # will autoregister
                p.graph.deserialise(v, True)

        self.graph.deserialise(d['GRAPH'], True)  # True to delete existing nodes first

        if 'INPUTS' in d and deserialiseInputs:
            self.inputMgr.deserialise(d['INPUTS'])

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

    ## generates a new unique name for a macro.
    def getUniqueUntitledMacroName(self):
        ct = 0
        while True:
            name = 'untitled' + str(ct)
            if name not in self.macros:
                return name
            ct += 1

    ## helper for external code - set input to some input type and run code to set data.
    def setInputData(self, inputidx, inputType, fn):
        i = self.inputMgr.inputs[inputidx]
        i.setActiveMethod(inputType)
        fn(i.getActive())  # run a function on active method
        # force an immediate read; it's OK, the data should be cached. This is done so we can return
        # a success/failure status/
        i.read()
        return i.exception

    def setInputENVI(self, inputidx, fname):
        """set graph's input to an ENVI"""
        return self.setInputData(inputidx, inputs.Input.ENVI, lambda method: method.setFileName(fname))

    def setInputRGB(self, inputidx, fname):
        """set graph's input to RGB"""
        return self.setInputData(inputidx, inputs.Input.RGB, lambda method: method.setFileName(fname))

    def setInputMulti(self, inputidx, directory, fnames):
        """set graph's input to multiple files"""
        return self.setInputData(inputidx, inputs.Input.RGB, lambda method: method.setFileNames(directory, fnames))

    def getNodeByName(self, name):
        """get a node by its DISPLAY name, not its internal UUID."""
        # this is a little ugly, but it's plenty quick enough and avoids problems
        for x in self.graph.nodes:
            if name == x.displayName:
                return x


