# You can install plugins into any directory in the pcotplugins path, which is specified
# inside the config file.

# By default this is just the PCOT/pcotplugins file in the user's home directory.


import cv2 as cv
import numpy as np

from pcot.sources import SourceSet
from pcot.xform import XFormType, xformtype
from pcot.xforms.tabdata import TabData
from pcot.imagecube import ImageCube
from pcot.datum import Datum
from pcot.datumtypes import Type
from PySide2.QtGui import QColor

import pcot.config


# The first part of the plugin creates a new type of node.

# this decorator will cause the node to auto-register.

@xformtype
class XFormEdgeDetect(XFormType):
    """This is an edge detector node. It takes an image and performs Canny edge detection, currently with
    fixed thresholds. It does not take account of ROIs, since this would be pointless when we're converting
    from a potentially multispectral image to greyscale (well, boolean).
    Exercise for the reader - add variable thresholds, either as numeric inputs or as
    numeric parameters settable from the node tab.

    DQ bits of the bands in the source are combined together for the single
    band of the result. Uncertainty is discarded.
    """

    def __init__(self):
        # this node should appear in the maths group.
        super().__init__("edge", "maths", "0.0.0")
        # set input and output - they are images and are unnamed.
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)

    def createTab(self, n, w):
        # there is no custom tab, we just use an data canvas. This expects "node.out" to be set to
        # either None or an imagecube.
        return TabData(n, w)

    def init(self, n):
        # No initialisation required.
        pass

    def perform(self, node):
        # get the input image
        img = node.getInput(0, Datum.IMG)
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
            # we build the new DQ by OR-ing all the bands' bits together
            dq = np.bitwise_or.reduce(img.dq, axis=2)
            # create the imagecube and set node.out for the canvas in the tab.
            img = ImageCube(out, None, img.sources, dq=dq)
            node.out = Datum(Datum.IMG, img)
        else:
            # no image on the input, set node.out to None
            node.out = Datum.null
        # output node.out
        node.setOutput(0, node.out)


################################################################################
# This section adds a new "expr" function "testf" which takes two numbers a,b
# and calculates a+b*2. The first part is very simple.
#
# The second part is a lot more complex, involving a custom Datum type.
#
# It adds a function "testf2" which takes a number a, an optional number b
# which defaults to 2, and divides a by b. It outputs a custom data type object
# called "testobject" consisting of dividend and remainder.

def testfunc(args, optargs):
    # the function itself, which takes a list of mandatory arguments and a
    # list of optional arguments (of which there are none)
    a = args[0].get(Datum.NUMBER)   # get the first argument, which is numeric
    b = args[1].get(Datum.NUMBER)   # and the second argument.
    result = a + b * 2                  # calculate the result

    # get the source sets from the inputs and combine them.
    sources = SourceSet([args[0].getSources(), args[1].getSources()])
    # convert the result into a numeric Datum and return it, attaching sources.
    return Datum(Datum.NUMBER, result, sources)
    
# now the other function with the custom type. 
# Our data will be an object of class TestObject.

class TestObject:
    def __init__(self, div, rem):
        self.div = div
        self.rem = rem
        
    def __str__(self):
        return f"({self.div}, {self.rem})"
    
# now the type singleton, which controls how Datum objects which hold TestObjects
# serialise and deserialise themselves (turn themselves into JSON-serialisable
# data and back).

# I'm naming the class with an underscore - the type object will be without this.
class _TestObjectType(Type):
    def __init__(self):
        # just call the superconstructor telling it the name of the type
        super().__init__('testtuple')

    def getDisplayString(self, d: 'Datum'):
        # how to turn this into a string for a graph box
        return "TUPLE"

    # now we have to write code which converts Datums of this type into
    # stuff which can be converted to JSON and back again. Converting
    # into JSON-serialisable is termed "serialisation" and reconstructing
    # the original Datum object and all its data is "deserialisation".

    def serialise(self, d):
        # how to serialise data of this type: serialise() methods must return
        # a tuple of typename and contents.
        # The contents must be JSON-serialisable, and must contain both the
        # data to be saved and the serialised source information.
        
        # First convert TestObject to something we can serialise
        serialisedObject = d.val.div, d.val.rem
        # and create the serialised datum of the name and contents
        return self.name, (serialisedObject, d.getSources().serialise())

    def deserialise(self, d, document):
        # given a serialised tuple generated by serialise(), produce a Datum
        # of this type.
        serialisedObject, serialisedSources = d        # first generate the contents
        # deserialise the serialised sources data
        sources = SourceSet.deserialise(serialisedSources, document)
        # then pass to the datum constructor along with the type singleton.
        return Datum(self, serialisedObject, sources) 

# create the singleton and register it, but keep hold of the variable so
# we can use it to create new Datum objects.
TestObjectType = _TestObjectType()
Datum.registerType(TestObjectType)

# add a brush for the connections in the graph
pcot.connbrushes.register(TestObjectType, QColor("darkMagenta"))

# and the function itself

def testfunc2(args, optargs):
    # get the mandatory "a" argument
    a = args[0].get(Datum.NUMBER)
    # and the optional "b" argument
    b = optargs[0].get(Datum.NUMBER)
    # perform the divisions
    div, rem = a/b, a%b
    # create the result
    res = TestObject(div,rem)
    # the sources are the union of the two incoming source sets - we can
    # pass a list of sourcesets into a sourceset constructor to get the union.
    sources = SourceSet([args[0].getSources(), optargs[0].getSources()])
    # create and return the datum, providing the type object we created.
    return Datum(TestObjectType, res, SourceSet)
    
    
# Now we have our two function definitions and associated things we can register them.    

def regfuncs(p):
    # late import of Parameter to avoid cyclic import problems.
    from pcot.expressions import Parameter
    # register our function.
    p.registerFunc("testf",                 # name
                   "calculates a+2*b",      # description
                   # a list defining our parameters by name, description and type
                   [Parameter("a", "number 1", Datum.NUMBER),
                    Parameter("b", "number 2", Datum.NUMBER)
                    ],
                   # the empty list of optional parameters
                   [],
                   # the function reference
                   testfunc)

    p.registerFunc("testf2",                            # name
                   "calculates a/b and remainder",      # description
                   # the sole mandatory parameter
                   [Parameter("a", "number 1", Datum.NUMBER)],
                   # the optional parameters in a new list with defaults
                   [Parameter("b", "number 2", Datum.NUMBER, deflt=2)],
                   # the function reference
                   testfunc2)


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

    menu = w.findOrAddMenu("Extras")
    menu.addAction('Graphviz', lambda: dumpToDot(w))


# This adds a hook to the system which is called whenever a new graph window is opened.
pcot.config.addMainWindowHook(addMenuItem)
