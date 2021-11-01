from typing import List, Optional, TYPE_CHECKING

from .envimethod import ENVIInputMethod
from .inputmethod import InputMethod
from .multifile import MultifileInputMethod
from .nullinput import NullInputMethod
from .rgb import RGBInputMethod
from pcot.imagecube import ImageCube

from pcot.ui.inputs import InputWindow


class Input:
    """This is an input, of which there are (probably) 4 or so.
    Each input has a number of "methods" - objects which can read RGB, multifiles
    and so on. All methods are always present, but only one is active.
    The data from the currently active input methods arrives in the graph through
    an XFormInput node.
    """
    window: Optional['InputWindow']     # if not None, an open window
    methods: List['InputMethod']        # list of methods
    activeMethod: int                   # index of active method in above array (see constants below)
    idx: int                            # index of input in the manager
    mgr: 'InputManager'                 # our input manager (we can use this to get the document)

    # indices of the methods in the 'methods' array; only activeMethod will be active.
    NULL = 0
    RGB = 1
    MULTIFILE = 2
    ENVI = 3

    def __init__(self, mgr, idx):
        """this will intialise an Input from scratch, typically when
        you're creating a new main graph. The input will be initialised
        to use the null method."""
        self.mgr = mgr
        self.idx = idx
        self.activeMethod = 0
        self.exception = None
        self.window = None
        self.methods = [
            NullInputMethod(self),  # null method must be first
            RGBInputMethod(self),
            MultifileInputMethod(self),
            ENVIInputMethod(self)
        ]

    def get(self):
        """Get the data for an input, reading into the cache if required."""
        # This needs to get a copy, otherwise its mapping will overwrite the mapping
        # in the input method itself.
        i = self.methods[self.activeMethod].get()
        if isinstance(i, ImageCube):
            return i.copy()
        else:
            return i

    def invalidate(self):
        """Invalidate ALL the methods for an input, whether they are active or not"""
        for m in self.methods:
            m.invalidate()

    def isActive(self, method):
        """return true if a given method is active"""
        return self.methods[self.activeMethod] == method

    def getActive(self):
        """return the active method"""
        return self.methods[self.activeMethod]

    def setActiveMethod(self, idx):
        """Set the active method: use the method index, see above - NULL, ENVI, etc..."""
        self.activeMethod = idx
        if self.window is not None:
            self.window.methodChanged()

    def selectMethod(self, method: InputMethod):
        """Given a method object, set the active method to that method"""
        self.setActiveMethod(self.methods.index(method))

    def openWindow(self):
        """Open the input window"""
        if self.window is None:
            self.window = InputWindow(self)
        # raise window to front and give it focus
        self.window.raise_()
        self.window.setFocus()

    def closeWindow(self):
        """Close the input window"""
        if self.window is not None:
            self.window.close()

    def onWindowClosed(self):
        """Called when the window is closed"""
        self.window = None

    def performGraph(self):
        """Performs the entire graph associated with the input's document.
        In an ideal world this would only perform those nodes in the graph
        which descend from the input nodes for this input. That's hairy,
        so I'll just perform the entire graph via changed() to ensure the
        inputs re-run."""
        self.mgr.doc.graph.changed()

    def serialise(self, internal):
        """Generate a serialisable data structure for this input (ie. primitives only).
        Done by producing a dict of lists of two elements: input type and input data.
        If 'internal' is set, images and cached images will also be stored - this is used
        to speed up undo/redo operations; we don't want them reloading data."""
        out = {'active': self.activeMethod,
               'methods': [[type(x).__name__, x.serialise(internal)] for x in self.methods]
               }
        return out

    ## rebuild this input from given data structure produced by serialise().
    # This will deserialise the input methods into the existing method objects,
    # to avoid problems with undo/redo leaving stale objects with widgets linked to
    # them.
    def deserialise(self, d, internal):
        """Rebuild this input from the data structure produced by serialise(). Set 'internal' if
        this is for undo/redo purposes (it will store image data too, to speed things up)."""
        # old way, where we recreate the method objects rather than just
        # putting new data into them.
        # self.methods = [self.createMethod(name, data) for name, data in d['methods']]

        self.activeMethod = d['active']
        methodsByName = {type(m).__name__: m for m in self.methods}
        for name, data in d['methods']:
            m = methodsByName[name]
            m.deserialise(data, internal)

    def createMethod(self, name, data=None):
        """create a method given its type name, and initialise it with some data. Currently unused."""
        klass = globals()[name]  # get type by name. Lawks!
        m = klass(self)  # construct object
        assert (isinstance(m, InputMethod))
        if data is not None:
            m.deserialise(data)  # and deserialise its data
        return m

    def __str__(self):
        """string for internal use only"""
        return "InputManager-active-{}".format(self.activeMethod)

    def brief(self):
        """string for use in captions, etc."""
        return self.getActive().brief()

    def long(self):
        """long description"""
        return self.getActive().long()


## how many inputs the system can have
NUMINPUTS = 4


class InputManager:
    """This is the input manager, which owns and manages the inputs.
    It itself is owned by a document"""
    inputs: List[Input]
    doc: 'Document'

    def __init__(self, doc):
        """Initialise, linking with a Document and creating a set of Inputs"""
        self.doc = doc
        self.inputs = [Input(self, i) for i in range(0, NUMINPUTS)]

    def openWindow(self, inputIdx):
        """Open a window for a given input index"""
        self.inputs[inputIdx].openWindow()

    def closeAllWindows(self):
        """Close all windows"""
        for x in self.inputs:
            x.closeWindow()

    def get(self, idx):
        """return the data for a given input."""
        return self.inputs[idx].get()

    def invalidate(self):
        """invalidate all inputs"""
        for x in self.inputs:
            x.invalidate()

    def serialise(self, internal):
        """serialise the inputs, returning a structure which can be converted into
        JSON (i.e. just primitive, dict and list types). This will contain a block
        of data for each input. Internal means that the data is used for undo/redo
        and may not be a true serialisation (there may be references). It never gets
        to a file or the clipboard. And restoring from it should not reload from disk/DAR!"""
        out = [x.serialise(internal) for x in self.inputs]
        return out

    def deserialise(self, lst, internal):
        """given a list like that produced by serialise(), generate the inputs. This will
        pass each block of data to each input"""
        for inp, data in zip(self.inputs, lst):
            inp.deserialise(data, internal)
