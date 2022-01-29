import logging
import time
from collections import deque
from typing import Dict

import pcot.config
from pcot import inputs, ui
from pcot.inputs.inp import InputManager
from pcot.macros import XFormMacro
from pcot.ui.mainwindow import MainUI
from pcot.utils import archive
from pcot.xform import XFormGraph

logger = logging.getLogger(__name__)


class UndoRedoStore:
    """Handles storing data for undo/redo processing. There are two stacks involved - 'undo' and 'redo.'
    How it works is described under each method, but the usage is:
    To mark that a change is about to happen, call mark() to record the state before the change.
    To indicate the last 'mark' was a mistake (because an error occurred during the operation), call unmark.
    To undo a change, call undo to get the previous state.
    To redo a change, call redo to get the new state.
    Use canUndo and canRedo to check the above calls are valid to make."""

    def __init__(self):
        """Initialise the system"""
        self.undoStack = deque(maxlen=8)
        self.redoStack = deque(maxlen=8)

    def clear(self):
        """Clear the two stacks, so that neither undo or redo are possible."""
        self.undoStack.clear()
        self.redoStack.clear()

    def canUndo(self):
        """return true if undo is possible (if there is data on the undo stack)"""
        logger.debug(f"UNDO STACK LEN: {len(self.undoStack)}")
        return len(self.undoStack) > 0

    def canRedo(self):
        """return true if redo is possible (if there is data on the redo stack)"""
        logger.debug(f"REDO STACK LEN: {len(self.redoStack)}")
        return len(self.redoStack) > 0

    def mark(self, state):
        """Document is about to change - record an undo point. All redo points
        are removed; this is a real external change made by a user."""
        self.undoStack.append(state)
        self.redoStack.clear()

    def unmark(self):
        """The last undo point is a mistake; perhaps an exception occurred during the
        change. Abandon and do not move to redo stack"""
        self.undoStack.pop()

    def undo(self, state):
        """Perform an undo, returning the new state or None. This pushes the current state (which must be
        passed in) to the redo stack, pops a state from the undo stack, and returns it."""
        if self.canUndo():
            x = self.undoStack.pop()
            self.redoStack.append(state)
        else:
            x = None
        return x

    def redo(self, state):
        """Perform a redo, returning the new state or None. This pushes the current state (which must be
        passed in) to the undo stack ,pops a state from the redo stack, and returns it."""
        if self.canRedo():
            x = self.redoStack.pop()
            self.undoStack.append(state)
        else:
            x = None
        return x

    def status(self):
        """return the sizes of undo and redo stacks"""
        return len(self.undoStack), len(self.redoStack)


class DocumentSettings:
    """this is saved to the SETTINGS block of the document"""

    def __init__(self):
        # integer indexing the caption type for canvases in this graph: see the box in MainWindow's ui for meanings.
        self.captionType = 0

    def serialise(self):
        return {
            'cap': self.captionType
        }

    def deserialise(self, d):
        self.captionType = d['cap']


class Document:
    """This class contains the main graph, inputs and macros for a PCOT document"""

    graph: XFormGraph
    macros: Dict[str, XFormMacro]
    inputMgr: InputManager
    settings: DocumentSettings
    undoRedoStore: UndoRedoStore

    def __init__(self, fileName=None):
        """Create a new document, and (optionally) load a file into it"""
        self.graph = XFormGraph(self, False)  # false - is not a macro
        self.inputMgr = InputManager(self)
        self.macros = {}
        self.settings = DocumentSettings()
        self.undoRedoStore = UndoRedoStore()

        if fileName is not None:
            self.load(fileName)
        else:
            self.graph.create("input 0")

    ## create a dictionary of everything in the app we need to save: global settings,
    # the graph, macros etc. If internal is true, this data is used for internal undo/redo
    # stuff and should operate very quickly without loading data. As such, it may not actually
    # perform a strict serialisation - you'll get information out with references in etc.
    def serialise(self, internal=False):
        macros = {}
        for k, v in self.macros.items():
            macros[k] = v.graph.serialise()

        d = {'SETTINGS': self.settings.serialise(),
             'INFO': {'author': pcot.config.getUserName(),
                      'date': time.time()},
             'GRAPH': self.graph.serialise(),
             'INPUTS': self.inputMgr.serialise(internal),
             'MACROS': macros
             }
        return d

    # deserialise everything from the given top-level dictionary into an existing graph;
    # also deserialises the macros (which are global to all graphs).
    # Deserialising the inputs is optional : we don't do it if we are loading templates
    # or if there is no INPUTS entry in the file, or there's no input manager (shouldn't
    # happen unless we're doing something weird like loading a macro prototype graph)
    def deserialise(self, d, deserialiseInputs=True, internal=False, closetabs=True):
        # deserialise macros before graph!
        if 'MACROS' in d:
            for k, v in d['MACROS'].items():
                p = XFormMacro(self, k)  # will autoregister
                p.graph.deserialise(v, True)

        # True to delete existing nodes first
        # and we also might not want to delete any tabs (for undo)
        self.graph.deserialise(d['GRAPH'], True, closetabs=closetabs)

        if 'INPUTS' in d and deserialiseInputs:
            self.inputMgr.deserialise(d['INPUTS'], internal)

        self.settings.deserialise(d['SETTINGS'])

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

    def setCaption(self, i):
        self.settings.captionType = i

    ## typically used in external code - just calls the graph changed()
    def changed(self):
        self.graph.changed()

    ## helper for external code - set input to some input type and run code to set data.
    def setInputData(self, inputidx, inputType, fn):
        i = self.inputMgr.inputs[inputidx]
        i.setActiveMethod(inputType)
        fn(i.getActive())  # run a function on active method
        # force an immediate read; it's OK, the data should be cached. This is done so we can return
        # a success/failure status/
        i.invalidate()
        i.get()
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
        """get a node by its DISPLAY name, not its internal UUID. Raises a NameError if not found."""
        # this is a little ugly, but it's plenty quick enough and avoids problems
        for x in self.graph.nodes:
            if name == x.displayName:
                return x
        raise NameError(name)

    def mark(self):
        """We are about to perform a change, so mark an undo/redo point"""
        self.undoRedoStore.mark(self.serialise(internal=True))
        self.showUndoStatus()

    def unmark(self):
        """The last placed mark was actually a mistake (perhaps led to an exception)
        so just remove it, but do not transfer it to the redo stack"""
        self.undoRedoStore.unmark()
        self.showUndoStatus()

    def replaceData(self, data):
        """Completely restore the document from a memento.
        In actuality only the graph changes and the document is actually the same, but
        the windows should all use the new graph."""

        # we don't delete any old tabs here.
        self.deserialise(data, internal=True, closetabs=False)
        for w in MainUI.getWindowsForDocument(self):
            w.replaceDocument(self)  # and this must repatch the tabs we didn't delete
        self.showUndoStatus()

    def canUndo(self):
        return self.undoRedoStore.canUndo()

    def canRedo(self):
        return self.undoRedoStore.canRedo()

    def undo(self):
        if self.canUndo():
            data = self.undoRedoStore.undo(self.serialise(internal=True))
            self.replaceData(data)
        self.showUndoStatus()

    def redo(self):
        if self.canRedo():
            data = self.undoRedoStore.redo(self.serialise(internal=True))
            self.replaceData(data)
        self.showUndoStatus()

    def clearUndo(self):
        self.undoRedoStore.clear()
        self.showUndoStatus()

    def showUndoStatus(self):
        for w in MainUI.getWindowsForDocument(self):
            w.showUndoStatus()
