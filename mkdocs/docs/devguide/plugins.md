# Writing PCOT plugins

## The plugin path
PCOT can be extended by adding Python scripts to a directory in the plugin
path. By default this is just ```pcotplugins``` in the user's home directory,
but it can be changed by editing the ```.pcot.ini``` file in that directory
and modifying the ```pluginpath``` value in the ```Locations``` section.
This should be a colon-separated list of directories.

## Adding new *expr* functions

Here is a snippet of code which will add a function to take two numbers a,b
and calculate a+b*2. It works by adding a registration function, which will
add our new function with its parameter types and help text. Note that as
in all PCOT code we have to make sure the sources are handled correctly.

```python
import pcot.config
from pcot.datum import Datum
from pcot.sources import SourceSet

# the function itself, which takes a list of mandatory arguments and a
# list of optional arguments (of which there are none)
def testfunc(args, optargs):
    a = args[0].get(Datum.NUMBER)   # get the first argument, which is numeric
    b = args[1].get(Datum.NUMBER)   # and the second argument.
    result = a + b * 2              # calculate the result

    # get the source sets from the inputs and combine them.
    sources = SourceSet([args[0].getSources(), args[1].getSources()])
    
    # convert the result into a numeric Datum and return it, attaching sources.
    return Datum(Datum.NUMBER, result, sources)

# This function will register new functions, of which we have only one.

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


# this will add a hook to the system to register these functions when the
# expression parser is created (which has to be done quite late).
pcot.config.addExprFuncHook(regfuncs)
```

For more examples of functions, look at the ```ExpressionEvaluator``` constructor
in the ```pcot.expressions.eval``` module.

## Adding new menu items

This is done by adding a function to a list of functions called when a
a main window is opened. Writing code here will require some knowledge of Qt.
Here is a menu option added to the File menu which will look for an
*input 0* node and save its output image (if there is one) to an ENVI file.


```python
import pcot
import os
from PySide2 import QtWidgets
from PySide2.QtWidgets import QAction, QMessageBox
from pcot.dataformats import envi

def saveEnvi(w):
    """Function takes a PCOT main window. It finds the input 0 if it can,
    and then saves an ENVI from that image."""
    
    try:
        node = w.doc.getNodeByName("input 0")
    except NameError:
        print("cannot find node")
        return
        
    res = QtWidgets.QFileDialog.getSaveFileName(w,
                                                "ENVI file ",
                                                os.path.expanduser(pcot.config.getDefaultDir('pcotfiles')),
                                                "ENVI files (*.hdr)")
    if res[0] != '':
        (root, ext) = os.path.splitext(res[0])
        # get the output of that input 0 node
        img = node.getOutput(0,pcot.datum.Datum.IMG)
        envi.write(root,img)
        
        
# the function to add the new menu item. This will take a single parameter:
# the window to which the menu should be added.

def addMenus(w):
    """Add an item to the Edit menu"""
    
    # create the menu action (i.e. the item)
    act = QAction("save to ENVI",parent=w)
    
    # find (or create) the Edit menu and add the action to it
    w.findOrAddMenu("Edit").addAction(act)
    
    # link the action to the saveEnvi function, using a closure to
    # make sure the window argument is passed into that function.
    act.triggered.connect(lambda: saveEnvi(w))
    

# Add the addMenus functions to the list of functions called as the
# main window opens.

pcot.config.addMainWindowHook(addMenus)
```

## Adding new node types

Node types are represented by singletons of subclasses of ```XFormType```
(Nodes themselves are of type ```XForm```, which stands for *transform* for
historical reasons). Developing new ```XFormType``` subclasses is largely
beyond the scope of this document, but you can learn a lot from looking at the
```pcot.xforms``` package and the modules therein.

To create a new node type, declare a new subclass of ```XFormType``` and decorate
it with the ```@xformtype``` decorator. This will make the type autoregister:
the singleton will be constructed and added to the internal type registry.

You will need to write the following methods in your subclass:

* **\_\_init\_\_(self)** to construct the type object (NOT the individual nodes).
This will call the superconstructor to set the type's name, group (for the
palette), and version. It will add the input and output connectors.
* **init(self, node)** will initialise any private data in the node itself
(which is an ```XForm```). Don't confuse this with ```__init__```!
* **createTab(self, node, window)** will create a new node area (i.e. tab).
Often, this can be a ```TabData``` which will look at the node's ```out```
attribute, which should be a ```Datum.```
* **perform(self, node)** will actually perform the node's action, reading inputs 
and setting outputs.

Remember: there is only one ```XFormType``` object for each node type. All nodes
are of type ```XForm```, and they link to an ```XFormType``` object to tell them
how to behave. This might seem a really odd way to do things, but it follows
"favour composition over inheritance" and saves messiness elsewhere.

Here is an example which does edge detection with OpenCV:

```
import cv2 as cv
import numpy as np

from pcot.sources import SourceSet
from pcot.xform import XFormType, xformtype, Datum
from pcot.xforms.tabdata import TabData
from pcot.imagecube import ImageCube

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
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)

    def createTab(self, n, w):
        # there is no custom tab, we just use a data canvas. This expects "node.out" to be set to
        # either None or a Datum.
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
            # create the imagecube and set node.out for the canvas in the tab
            img = ImageCube(out, None, img.sources)
            node.out = Datum(Datum.IMG, img)
        else:
            # no image on the input, set node.out to None
            node.out = Datum.null
        # output node.out
        node.setOutput(0, node.out)
```
