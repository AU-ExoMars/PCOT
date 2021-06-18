import cv2 as cv
import numpy as np

from pcot.xform import XFormType, xformtype, Datum
from pcot.xforms.tabimage import TabImage
import pcot.conntypes as conntypes
from pcot.pancamimage import ImageCube

from PyQt5 import QtWidgets

import pcot.config


# The first part of the plugin creates a new type of node.

# this decorator will cause the node to auto-register.

@xformtype
class XFormEdgeDetect(XFormType):
    """This is an edge detector node. It takes an image and performs Canny edge detection, currently with
    fixed thresholds. It does not take account of ROIs, since this would be pointless when we're converting
    from a potentially multispectral image to greyscale (well, boolean).
    Exercise for the reader - add variable thresholds, either as numeric inputs or as
    numeric parameters settable from the node tab."""

    def __init__(self):
        # this node should appear in the maths group.
        super().__init__("edge", "maths", "0.0.0")
        # set input and output - they are images and are unnamed.
        self.addInputConnector("", conntypes.IMG)
        self.addOutputConnector("", conntypes.IMG)

    def createTab(self, n, w):
        # there is no custom tab, we just use an image canvas. This expects "node.img" to be set to
        # either None or an imagecube.
        return TabImage(n, w)

    def init(self, n):
        # No initialisation required.
        pass

    def perform(self, node):
        # get the input image
        img = node.getInput(0, conntypes.IMG)
        if img is not None:
            # find mean of all channels - construct a transform array and then use it.
            mat = np.array([1 / img.channels] * img.channels).reshape((1, img.channels))
            grey = cv.transform(img.img, mat)
            # convert to 8-bit integer from 32-bit float
            img8 = (grey * 255).astype('uint8')
            # Perform edge detection
            out = cv.Canny(img8, 100, 200)
            # Convert back to 32-bit float
            out = (out / 255).astype('float32')
            # create the imagecube and set node.img for the canvas in the tab
            node.img = ImageCube(out, None, img.sources)
        else:
            # no image on the input, set node.img to None
            node.img = None
        # output node.img
        node.setOutput(0, Datum(conntypes.IMG, node.img))


################################################################################
# This section adds a new "expr" function which takes two numbers a,b and
# calculates a+b*2.

def testfunc(args, optargs):
    # the function itself, which takes a list of mandatory arguments and a
    # list of optional arguments (of which there are none)
    a = args[0].get(conntypes.NUMBER)   # get the first argument, which is numeric
    b = args[1].get(conntypes.NUMBER)   # and the second argument.
    result = a + b * 2                  # calculate the result
    # convert the result into a numeric Datum and return it.
    return Datum(conntypes.NUMBER, result)


def regfuncs(p):
    # late import of Parameter to avoid cyclic import problems.
    from pcot.expressions.parse import Parameter
    # register our function.
    p.registerFunc("testf",                 # name
                   "calculates a+2*b",      # description
                   # a list defining our parameters by name, description and type
                   [Parameter("a", "number 1", conntypes.NUMBER),
                    Parameter("b", "number 2", conntypes.NUMBER)
                    ],
                   # the empty list of optional parameters
                   [],
                   # the function reference
                   testfunc)


# this will add a hook to the system to register these functions when the expression parser
# is created (which has to be done quite late).
pcot.config.addExprFuncHook(regfuncs)


################################################################################
# This part of the plugin allows users to output a graph as a graphviz file
# for processing with "dot". It relies on a fairly deep understanding of the data
# model (and also graphviz!). The dump is made to stdout.

def makeNodeLabel(n):
    # generate a record-style label for a node based on the node type and connectors
    name = n.type.name
    ins = [x[0] for x in n.type.inputConnectors]
    outs = [x[0] for x in n.type.outputConnectors]

    qq = []
    for x in range(len(ins)):
        qq.append("<i{}>{}".format(x, ins[x]))
    ins = qq

    qq = []
    for x in range(len(outs)):
        qq.append("<o{}>{}".format(x, outs[x]))
    outs = qq

    ins = "{" + "|".join(ins) + "}|" if len(ins) > 0 else ""
    outs = "|{" + "|".join(outs) + "}" if len(outs) > 0 else ""
    return '{{{}{}{}}}'.format(ins, name, outs)


def dumpNodeDot(n):
    # output a node
    print('n{} [label="{}" shape="record"]'.format(n.name, makeNodeLabel(n)))


def dumpNodeDotConnections(n):
    # output a node's connections
    for inidx in range(len(n.type.inputConnectors)):
        if n.inputs[inidx] is not None:
            outnode, outidx = n.inputs[inidx]
            print('n{}:o{} -> n{}:i{}'.format(outnode.name, outidx, n.name, inidx))


def dumpToDot(w):
    # output window's graph to graphviz.
    g = w.graph
    print("digraph G {")
    for x in g.nodes:
        dumpNodeDot(x)
    for x in g.nodes:
        dumpNodeDotConnections(x)

    print("}")


def addMenuItem(w):
    # Add an extra menu to the window, and a single menu item. The argument for this function is
    # the window, from which we can easily get the graph.
    menu = w.menubar.addMenu("Extras")
    menu.addAction('Graphviz', lambda: dumpToDot(w))


# This adds a hook to the system which is called whenever a new graph window is opened.
pcot.config.addMainWindowHook(addMenuItem)
