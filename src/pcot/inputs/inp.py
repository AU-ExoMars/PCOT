from typing import List, Optional, TYPE_CHECKING

from .inputmethod import InputMethod
from pcot.ui.inputs import InputWindow
from ..datum import Datum


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
    PDS4 = 4
    DATUMARCH = 5
    DIRECT = 6

    def __init__(self, mgr, idx):
        """this will intialise an Input from scratch, typically when
        you're creating a new main graph. The input will be initialised
        to use the null method."""
        from .datumarchive import DatumArchiveInputMethod
        from .directinput import DirectInputMethod
        from .envimethod import ENVIInputMethod
        from .multifile import MultifileInputMethod
        from .nullinput import NullInputMethod
        from .rgb import RGBInputMethod
        from .pds4input import PDS4InputMethod

        self.mgr = mgr
        self.idx = idx
        self.activeMethod = 0
        self.exception = None
        self.window = None
        self.methods = [
            NullInputMethod(self),  # null method must be first
            RGBInputMethod(self),
            MultifileInputMethod(self),
            ENVIInputMethod(self),
            PDS4InputMethod(self),
            DatumArchiveInputMethod(self),
            DirectInputMethod(self),
        ]

    def get(self) -> Datum:
        """Get the data for an input - the underlying method may cache or copy."""
        return self.methods[self.activeMethod].get()

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

    def serialise(self, internal, saveInputs=True):
        """Generate a serialisable data structure for this input (ie. primitives only).
        Done by producing a dict of lists of two elements: input type and input data.
        If 'internal' is set, images and cached images will also be stored - this is used
        to speed up undo/redo operations; we don't want them reloading data."""

        # if we are saving to a file, actually save the input data too. We don't want to do
        # this when we are doing an internal (undo) serialise because the data there is 'saved'
        # internally as simple references to the objects; this is done in the methods. Note that
        # we only save the active method's data in the external (save to file) case.
        
        if saveInputs and not internal:
            activeData = self.get().serialise()  # returns Datum
        else:
            activeData = None

        out = {'active': self.activeMethod,
               'methods': [[type(x).__name__, x.serialise(internal)] for x in self.methods],
               'activeData': activeData
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

        if 'activeData' in d and d['activeData'] is not None:
            # if this was an external save, there will be an actual Datum here we can use - until
            # a method changes!
            data = Datum.deserialise(d['activeData'], self.mgr.doc)
            # and set this datuerm in the active method
            self.methods[self.activeMethod].data = data

    def createMethod(self, name, data=None):
        """create a method given its type name, and initialise it with some data. Currently unused."""
        klass = globals()[name]  # get type by name. Lawks!
        m = klass(self)  # construct object
        assert (isinstance(m, InputMethod))
        if data is not None:
            m.deserialise(data)  # and deserialise its data
        return m

    def __repr__(self):
        """string for internal use only"""
        return f"Input-{self.idx}-active-{self.activeMethod}"


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

    def getInput(self, idx):
        """return the actual Input object, which contains the input methods"""
        return self.inputs[idx]

    def invalidate(self):
        """invalidate all inputs"""
        for x in self.inputs:
            x.invalidate()

    def serialise(self, internal, saveInputs=True):
        """serialise the inputs, returning a structure which can be converted into
        JSON (i.e. just primitive, dict and list types). This will contain a block
        of data for each input. Internal means that the data is used for undo/redo
        and may not be a true serialisation (there may be references). It never gets
        to a file or the clipboard. And restoring from it should not reload from disk/DAR!"""
        out = [x.serialise(internal, saveInputs=saveInputs) for x in self.inputs]
        return out

    def deserialise(self, lst, internal):
        """given a list like that produced by serialise(), generate the inputs. This will
        pass each block of data to each input"""
        for inp, data in zip(self.inputs, lst):
            inp.deserialise(data, internal)
