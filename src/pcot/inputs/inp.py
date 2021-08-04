## the abstract class from which all input types come
from typing import List, Optional, TYPE_CHECKING

from .envi import ENVIInputMethod
from .inputmethod import InputMethod
from .multifile import MultifileInputMethod
from .nullinput import NullInputMethod
from .rgb import RGBInputMethod
from pcot.pancamimage import ImageCube

if TYPE_CHECKING:
    from pcot.xform import XFormGraph

from pcot.ui.inputs import InputWindow


## This is an input, of which there are (probably) 4 or so.
# Each input has a number of "methods" - objects which can read RGB, multifiles
# and so on. All methods are always present, but only one is active.
# The data from the currently active input methods arrives in the graph through
# an XFormInput node.

class Input:
    window: Optional['InputWindow']
    methods: List['InputMethod']
    activeMethod: int

    NULL = 0
    RGB = 1
    MULTIFILE = 2
    ENVI = 3

    ## this will intialise an Input from scratch, typically when
    # you're creating a new main graph. The input will be initialised
    # to use the null method.

    def __init__(self, mgr):
        self.mgr = mgr
        self.activeMethod = 0
        self.exception = None
        self.window = None
        self.methods = [
            NullInputMethod(self),  # null method must be first
            RGBInputMethod(self),
            MultifileInputMethod(self),
            ENVIInputMethod(self)
        ]

    ## actually returns the cached data. Will not read, though - that should be done by readAll.
    def get(self):
        # This needs to get a copy, otherwise its mapping will overwrite the mapping
        # in the input method itself.
        i = self.methods[self.activeMethod].get()
        if isinstance(i, ImageCube):
            return i.copy()
        else:
            return i

    def read(self):
        self.exception = None
        try:
            self.methods[self.activeMethod].read()
        except Exception as e:
            self.exception = e

    def isActive(self, method):
        return self.methods[self.activeMethod] == method

    def getActive(self):
        return self.methods[self.activeMethod]

    # use from external code with NULL, ENVI, etc...
    def setActiveMethod(self, idx):
        self.activeMethod = idx
        if self.window is not None:
            self.window.methodChanged()

    def selectMethod(self, method: InputMethod):
        self.setActiveMethod(self.methods.index(method))

    def openWindow(self):
        if self.window is None:
            self.window = InputWindow(self)
        # raise window to front and give it focus
        self.window.raise_()
        self.window.setFocus()

    def closeWindow(self):
        if self.window is not None:
            self.window.close()

    def onWindowClosed(self):
        self.window = None

    ## in an ideal world this would only perform those nodes in the graph
    # which descend from the input nodes for this input. That's hairy,
    # so I'll just perform the entire graph via changed() to ensure the
    # inputs re-run.
    def performGraph(self):
        self.mgr.graph.changed()

    ## serialise the input, or rather produce a "serialisable" data structure. We
    # do this by producing a list of two elements: the input type and that input type's
    # data.
    def serialise(self, internal):
        out = {'active': self.activeMethod,
               'methods': [[type(x).__name__, x.serialise(internal)] for x in self.methods]
               }
        return out

    ## rebuild this input from given data structure produced by serialise().
    # This will deserialise the input methods into the existing method objects,
    # to avoid problems with undo/redo leaving stale objects with widgets linked to
    # them.
    def deserialise(self, d, internal):
        # old way creating new objects
        # self.methods = [self.createMethod(name, data) for name, data in d['methods']]

        self.activeMethod = d['active']
        methodsByName = {type(m).__name__: m for m in self.methods}
        for name, data in d['methods']:
            m = methodsByName[name]
            m.deserialise(data, internal)

    ## create a method given its type name, and initialise it with some data.
    def createMethod(self, name, data=None):
        klass = globals()[name]  # get type by name. Lawks!
        m = klass(self)  # construct object
        assert (isinstance(m, InputMethod))
        if data is not None:
            m.deserialise(data)  # and deserialise its data
        return m

    def __str__(self):
        return "InputManager-active-{}".format(self.activeMethod)


## how many inputs the system can have
NUMINPUTS = 4


## This is the input manager, which owns and manages the inputs. It itself is owned by a graph,
# if that graph isn't a macro prototype graph.

class InputManager:
    inputs: List[Input]
    graph: 'XFormGraph'

    def __init__(self, doc):
        self.graph = doc.graph
        self.inputs = [Input(self) for _ in range(0, NUMINPUTS)]

    def openWindow(self, inputIdx):
        self.inputs[inputIdx].openWindow()

    def closeAllWindows(self):
        for x in self.inputs:
            x.closeWindow()

    def get(self, idx):
        return self.inputs[idx].get()

    ## serialise the inputs, returning a structure which can be converted into
    # JSON (i.e. just primitive, dict and list types). This will contain a block
    # of data for each input. Internal means that the data is used for undo/redo
    # and may not be a true serialisation (there may be references). It never gets
    # to a file or the clipboard. And restoring from it should not reload from disk/DAR!
    def serialise(self, internal):
        out = [x.serialise(internal) for x in self.inputs]
        return out

    ## given a list like that produced by serialise(), generate the inputs. This will
    # pass each block of data to each input
    def deserialise(self, lst, internal):
        for inp, data in zip(self.inputs, lst):
            inp.deserialise(data, internal)

    ## force reread of all inputs, typically on graph.changed().
    def readAll(self):
        for x in self.inputs:
            x.read()
