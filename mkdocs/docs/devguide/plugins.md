# Writing PCOT plugins

## The plugin path
PCOT can be extended by adding Python scripts to a directory in the plugin
path. By default this is just ```pcotplugins``` in the user's home directory,
but it can be changed by editing the ```.pcot.ini``` file in that directory
and modifying the ```pluginpath``` value in the ```Locations``` section.
This should be a semicolon-separated list of directories.

@@@warning
You may be tempted to use quotes in the names of you plugin directories:
don't. It should work fine, even if your directories have spaces in them.
For example, use ```~/blah/RIM Dewarping``` and not 
```~/blah/"RIM Dewarping"```
@@@

## Adding new types 

This is covered in [a separate document](types.md), as it's not often done
and is a little involved.

## Adding new Datum functions (for use in *expr* and Python code)

The functions used in the *expr* expression node can also be used in
Python programs which use PCOT as a library (this is 
[covered here](library.md)). These are called Datum functions because
they both take and return Datum objects.

To create a Datum function:

* use the `@datumfunc` decorator. This will
register the function and wrap it in two separate wrappers: one for use
in *expr*, the other for use in Python.
* write a docstring in the correct format, as illustrated below.

Here's an example which declares a function to take two numbers
a,b and calculate a+b*2. Note that as
in all PCOT code we have to make sure the sources are handled correctly.

```python
@datumfunc
def example_func(a, b):
    """
    Example function that takes two numbers a,b and returns a+b*2
    @param a: number: first number
    @param b: number: second number
    """
    return a + b * Datum.k(2)
```

This is a trivial example that relies on Datum objects having operator
overloads, but note that we need to multiply b by a Datum, not a number.
To do this we use `Datum.k` to create a scalar constant.

### The docstring

This should consist of a number of lines describing the function followed
by a number of `@param` lines, one for each parameter. These contain
the following, separated by colons:

* The string `@param'
* A Datum type name - these can be found in the constructors of datum type
objects in `datumtypes.py`, but the most common are `number`, `img`, `roi`,
`string`.
* A description of the parameter

### Optional numeric/string arguments

Optional arguments with defaults can be provided, but only if they
are numeric or strings (because these are the only types which make
sense for the default values). In this case the defaults will be
converted to Datum objects if they are used.

Here is an example of a function which
multiplies an image by a constant, with the default being 2:

```
@datumfunc
def example_func(img, k=2):
    """
    Example function that takes two numbers a,b and returns a+b*2
    @param img:img:the image
    @param k:number:the multiplier
    """
    # no need to construct a Datum with Datum.k(), because k is already
    # a Datum.
    return img * k
```
Here's another example which adds two numbers or multiplies them,
depending on a string - and the default is to add:

```
@datumfunc
def stringexample(a, b, op='add'):
    """
    String argument example
    @param a: number: first number
    @param b: number: second number
    @param op: string: operation to perform
    """
    if op.get(Datum.STRING) == 'add':
        return a + b
    elif op.get(Datum.STRING) == 'sub':
        return a - b
    else:
        raise ValueError("Unknown operation")
```
Note that you usually have to extract the actual value from the Datum
objects, as we do with the `op` argument above. In previous examples,
we take advantage of Datum's extensive operator overloading.

### Variadic arguments

For a variable number of arguments, use the `*args` keyword. Here, you have
to check the types by hand. For example, this function will sum numbers:
```
@datumfunc
def sumall(*args):
    """
    Sum all arguments
    """
    s = sum([x.get(Datum.NUMBER).n for x in args])
    return Datum(Datum.NUMBER, Value(s, 0, NOUNCERTAINTY), nullSourceSet)
```
Note the use of `Value` here to construct a scalar value with
standard deviation (zero here) and DQ bits (indicating no uncertainty data).
Also note the mandatory use of a source set - just the `nullSourceSet`
here to indicate there is no source; this is just a test function. In a real
function we would combine the input sources.

For more examples of functions, look at the ```ExpressionEvaluator```
constructor in the ```pcot.expressions.eval``` module.

## Adding new menu items

This is done by adding a function to a list of functions called when a
a main window is opened. Writing code here will require some knowledge of Qt.
Here is a menu option added to the File menu which will look for 
selected node in the document's graph, fetch its first output, and
save it as an ENVI file (assuming it is an image - error checking
is left as an exercise for the reader).


```python
import pcot
import os
from PySide2 import QtWidgets
from PySide2.QtWidgets import QAction, QMessageBox
from pcot.dataformats import envi

def saveEnvi(w):
    """Function takes a PCOT main window. It finds the first selected
    node, gets its output 0, and then saves an ENVI from that image."""
    
    sel = w.doc.getSelection()
    if len(sel) == 0:
        ui.log("no selected node")
        return
    node = sel[0]
        
    directory = os.path.expanduser(pcot.config.getDefaultDir('pcotfiles'))
    res = QtWidgets.QFileDialog.getSaveFileName(w,
                                                "ENVI file ",
                                                os.path.expanduser(pcot.config.getDefaultDir('pcotfiles')),
                                                "ENVI files (*.hdr)")
    if res[0] != '':
        # get the output of that node
        (root, ext) = os.path.splitext(res[0])
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

Remember: there is only one ```XFormType``` object for each node type. All
nodes are of type ```XForm```, and they link to an ```XFormType``` object to
tell them how to behave. This might seem a really odd way to do things, but it
follows "favour composition over inheritance" and saves messiness elsewhere.

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

### Writing custom Tabs

As noted above, a new `XFormType` subclass (i.e. a new node type)
can often just use `TabData`, which will display the Datum stored on
its first output (output 0). Sometimes, however, a custom tab needs to be
written. This can be a complex task, but an example is given in
`xformexample.py` in the `xforms` package. All the standard XFormTypes
are in this package, so you can also look at them. 

The basic idea is:

* Create a subclass of `pcot.ui.tabs.Tab`
* Write the constructor to call the superclass constructor and create the UI
(or load a Designer-created UI by passing an argument to the superclass.
constructor), and call `self.nodeChanged()` at the end to refresh the tab from the node.
* Override `onNodeChanged()` to update the tab from the node.
* Use the Qt signal/slot mechanism to connect the tab's controls to methods in the tab class
and write code to update the node from the tab in these methods, calling
`self.changed()` at the end of each method.

The tab will have a `node` field which addresses the node it is viewing (but see
[below](#undo-and-references-to-data-in-nodes) for a "gotcha" - the value of this field
will change after an undo operation!)

### Using Canvas in custom tabs

Creating a Canvas programmatically is straightforward, and there is an example of this
in `xformexample.py`. 
If you are creating a tab in Designer, you need to add a canvas as a QWidget which you then "promote"
to a custom control (the canvas). In the promote dialog, the class should be `Canvas` and the
header file `pcot.ui.canvas` (i.e. the package name). 


In your `onNodeChanged()` method you
will need to update the canvas. This involves doing a little setup, then getting the 
image we want to display - usually the output - and telling the canvas to display it:
```
    # do some setup
    self.canvas.setNode(self.node)

    # then display the image
    img = self.node.getOutput(0, Datum.IMG)
    self.canvas.display(img)
```

The setup synchronises the canvas with the node, telling the canvas about the RGB mappings
and that it should store data in the node for serialisation. We have to set that up each
time because of how undo works, which is discussed in the next section.

### Undo and references to data in nodes

This is a major "gotcha." Whenever an undo occurs, the old node is discarded and a new node
created from a previously archived version in memory. This means that the `node` field changes.
Because of this, your tab **must not** store references to objects inside the node, because after
an undo those references will be stale. Instead, always use `self.node...` to access data.

It is OK to use the tab to store UI-only data which is not persisted (saved to a file or to the
undo mechanism).

### Serialisation and deserialisation

Your node may have parameters which need to be saved to .pcot files or saved
into the undo data. To do this, PCOT needs to convert them into data
which is "JSON-serialisable" - convertable to text in the JSON format.
PCOT refers to the process of conversion into JSON-serialisable data
as "serialisation," even though it's really only the first step. It's just
that the JSON library takes care of the rest of the process.

JSON-serialisable data consists of built-in Python types: strings, numbers,
lists, dicts and tuples.

PCOT has no less than four mechanisms for converting node data into JSON:
[read more about them here](nodeser.md).
