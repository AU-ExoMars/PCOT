## the abstract class from which all input types come
from typing import List, Optional, TYPE_CHECKING

from inputs.inputmethod import InputMethod
from inputs.multifile import MultifileInputMethod
from inputs.nullinput import NullInputMethod
from inputs.rgb import RGBInputMethod

if TYPE_CHECKING:
    from xform import XFormGraph

from ui.inputs import InputWindow


## This is an input, of which there are (probably) 4 or so.
# Each input has a number of "methods" - objects which can read RGB, multifiles
# and so on. All methods are always present, but only one is active.
# The data from the currently active input methods arrives in the graph through
# an XFormInput node.

class Input:
    window: Optional['InputWindow']
    methods: List['InputMethod']
    activeMethod: int

    ## this will intialise an Input from scratch, typically when
    # you're creating a new main graph. The input will be initialised
    # to use the null method.

    def __init__(self, mgr):
        self.mgr = mgr
        self.activeMethod = 0
        self.window = None
        self.methods = [
            NullInputMethod(self),  # null method must be first
            RGBInputMethod(self),
            MultifileInputMethod(self)
        ]

    def get(self):
        return self.methods[self.activeMethod].get()

    def isActive(self, method):
        return self.methods[self.activeMethod] == method

    def selectMethod(self, method):
        self.activeMethod = self.methods.index(method)
        self.window.methodChanged()

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
    # so I'll just perform the entire graph.
    def performGraph(self):
        self.mgr.graph.performNodes()

    ## serialise the input, or rather produce a "serialisable" data structure. We
    # do this by producing a list of two elements: the input type and that input type's
    # data.
    def serialise(self):
        out = {'active': self.activeMethod,
               'methods': [[type(x).__name__, x.serialise()] for x in self.methods]
               }
        return out

    ## rebuild this input from given data structure produced by serialise().
    # We could just deserialise the data into the existing objects, but this is
    # probably safer, avoiding stale data.
    def deserialise(self, d):
        self.activeMethod = d['active']
        self.methods = [self.createMethod(name, data) for name, data in d['methods']]

    ## create a method given its type name, and initialise it with some data.
    def createMethod(self, name, data=None):
        klass = globals()[name]  # get type by name. Lawks!
        m = klass(self)  # construct object
        assert (isinstance(m, InputMethod))
        if data is not None:
            m.deserialise(data)  # and deserialise its data
        return m


## how many inputs the system can have
NUMINPUTS = 4


## This is the input manager, which owns and manages the inputs. It itself is owned by a graph,
# if that graph isn't a macro prototype graph.

class InputManager:
    inputs: List[Input]
    graph: 'XFormGraph'

    def __init__(self, graph):
        self.graph = graph
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
    # of data for each input.
    def serialise(self):
        out = [x.serialise() for x in self.inputs]
        return out

    ## given a list like that produced by serialise(), generate the inputs. This will
    # pass each block of data to each input
    def deserialise(self, lst):
        for inp, data in zip(self.inputs, lst):
            inp.deserialise(data)

    ## force reread of all inputs, typically on graph.changed().
    def getAll(self):
        for x in self.inputs:
            x.get()
