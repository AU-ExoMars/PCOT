## the abstract class from which all input types come
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from xform import XFormGraph

import ui
from pancamimage import ImageCube, ChannelMapping
from ui.inputs import InputWindow, PlaceholderMethodWidget, RGBMethodWidget


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

    # in an ideal world this would only perform those nodes in the graph
    # which descend from the input nodes for this input. That's hairy,
    # so I'll just perform the entire graph.
    def performGraph(self):
        self.mgr.graph.performNodes()

    def serialise(self):
        raise Exception("NOT YET IMPLEMENTED")
        return None


class InputMethod:
    def __init__(self, inp):
        self.input = inp

    def isActive(self):
        return self.input.isActive(self)

    def get(self):
        pass

    def getName(self):
        pass

    def createWidget(self):
        pass


## the Null input, which does nothing and outputs None

class NullInputMethod(InputMethod):
    def __init__(self, inp):
        super().__init__(inp)

    def get(self):
        return None

    def getName(self):
        return "null"

    def createWidget(self):
        return PlaceholderMethodWidget(self)


## the RGB input method

class RGBInputMethod(InputMethod):
    img: ImageCube
    fname: str
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None
        self.fname = None
        self.mapping = ChannelMapping()

    def loadImg(self):
        # will throw exception if load failed
        img = ImageCube.load(self.fname, self.mapping)
        ui.log("Image {} loaded: {}".format(self.fname, img))
        self.img = img

    def get(self):
        if self.img is None and self.fname is not None:
            self.loadImg()
        return self.img

    def getName(self):
        return "RGB"

    def createWidget(self):
        return RGBMethodWidget(self)


## the Multifile input method

class MultifileInputMethod(InputMethod):
    def __init__(self, inp):
        super().__init__(inp)

    def get(self):
        return None

    def getName(self):
        return "Multifile"

    def createWidget(self):
        return PlaceholderMethodWidget(self)


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
