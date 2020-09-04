# Architecture for PCOT prototype

This document briefly describes the architecture of the PCOT prototype,
discussing the main classes and how certain complex operations are performed
(e.g. serialisation and deserialisation, aka. saving and loading). It 
does not discuss how to use the program and is intended for people who
wish to write more plugin modules, fix bugs or add features.

## Module and package architecture

The main top-level modules of the program are:

* **main** contains the main window user interface code.
* **xform** contains the data model definition, i.e. how the nodes, node types
and graph fit together. All UI code is in other modules. Note that the
graph nodes are correctly referred to as **xform nodes** (transform nodes).
* **graphscene** contains the code for managing the Qt Graphics Scene
objects for the graph view panel, and handling user interface actions for
those objects.
* **graphview** contains code for managing view-level events for the graph
view panel, and as such is tightly coupled to graphscene.
* **palette** handles the note type palette - the list of node types visible
next to the graph view.

There the following subpackages:

* **ui** contains user interface utility types for managing dockable tabs,
matplotlib widgets, OpenCV canvas widgets etc.
* **utils** contains utility classes which are not user interfaces
(such as hierarchical clustering)
* **xforms** contains the node type definitions, which are all automatically
imported and registered. This will be described in more detail below.

In addition, the **assets** directory contains the user interface **.ui**
which describe the user interface layouts for various windows and tabs.
These are XML files created in Qt Designer.

## The Model

### XForm nodes

The data model is a directed acyclic graph consisting of transformation
nodes which act on data. The entire graph is an object of class 
**XFormGraph**. Each node is an object of type **XForm**.
Each node type is a singleton subclass of **XFormType**, and each 
individual node has a link to the appropriate node type object.
Thus the different node types' behaviours are handled by the node type
object to which the node is connected, not by the node itself (this may
seem a slightly odd architecture, but using inheritance polymorphism to
achieve this - i.e. subclasses of XNode - introduces more problems) (favour composition over inheritance).

Each XForm node is primarily connected to others in the graph through its
inputs: the **inputs** attribute contains a list of tuple pairs (node,index)
where *node* is the connected node and *index* is the index of the output
connection on that node. Each node also contains some information about
its output connections in the **children** dict: this is a dictionary mapping
from node to an integer number of connections. If there is no connection,
there is no dictionary entry. Consider two nodes A and B.
If node A's output 2 is connected to node B's input 1, the relevant
data is:
* Entry 1 in node B's inputs array will contain (A,2)
* The children dictionary in node A will contain B:1, indicating that node
A has a single outgoing connection to node B.

### XFormType objects

The **xforms** directory contains the node type definition modules. Each
module contains the definition of an XFormType subclass, preceded by 
the **@xformtype** decorator. This decorator automatically constructs
the only instance of the class, redirects the constructor call to return
this instance, and also calculates the MD5 checksum of the source code for
the file, storing it in the singleton. The XFormType constructor also
registers the class by name in the **allTypes** dictionary at startup.

Therefore it should not be necessary to refer to any XFormType subclass
in the code directly: when a node is created, the XForm constructor
looks up the node in the dictionary and creates the required linkage.

Each XFormType subclass **must** define the following methods:
* **__init\_\_(self,name,ver)**: the constructor for the type, which
runs at startup. This should take a unique name for the type and a
three-part version number (see Versioning below).
* **init(self,xform)**: given an XForm node, initialise attributes within the
node which are private to this type. In other words, initialise the node.
* **perform(self,xform)**: perform the node's action, reading inputs and
generating outputs for that node. The former is done using **getInput**,
the latter with **setOutput** on the node. Bear in mind that the latter will also cause the
all nodes below this to perform their actions, and so the entire subtree will
recursively run.
* **createTab(self,xform)**: create the user interface tab. Occasionally
a node type may omit this if there is no reasonable user interface at all,
but his is very rare. The result should be a subclass of *ui.tabs.Tab*, a
dockable tab.

It may also implement:

* **generateOutputTypes(self,xform)**: some nodes may change their output
types depending on their inputs. This is called when an input connection
is made or broken, and uses either **changeOutputType(outindex,typeobj)**
to achieve this, or more commonly **matchOutputsToInputs()**. This latter
method takes a list of pairs of input and output indices and makes the 
latter the same type as the former.
* **recalculate(xform)** is used if internal data to a node should be changed
after the node UI has been edited or it has been loaded (a typical example
is lookup tables). It is called in onNodeChanged() in the tab class, and
also when the node is loaded. In the former case this should be done after
the controls in the tab are read, but before changing any status displays.
* **serialise(xform)** is used to serialise additional data on saving.
It should return a dict of names to plain data (see the JSON Python documentation
for what can be serialised). It should be avoided if possible, see below.
* **deserialise(xform,d)** is used to deserialise additional data serialised
with serialise(). 

#### Automatic serialisation

Any special data in the node which should be saved which is "plain data"
(see the Python JSON docs) can be serialised and deserialised automaticaly
by listing the attribute names in a tuple called **autoserialise**. This
shiuld be set up in the XFormType's constructor. This approach is favoured
over implementing the **serialise** and **deserialise** members, which
should only be used when the data requires extra processing.

### The xforms package

All Python files in this package directory with names of the form **xform<name>.py** 
are transform node (and associated UI) definitions, and are loaded automatically 
from the **__init()\_\_** function of the package. This makes it easy to extend
the program: simply write new node types in this directory. 

#### Versioning

This can introduce versioning problems: people may edit nodes, which may cause
data products to change. Two measures are taken to avoid this:
* Each node type must provide a **ver** attribute, set in the node type constructor. This
is a three part [semantic version](https://semver.org/):
    * MAJOR version when you make incompatible API changes,
    * MINOR version when you add functionality in a backwards compatible manner, and
    * PATCH version when you make backwards compatible bug fixes.
This is not used for version checking, merely to provide a reference.
* An MD5 checksum is automatically generated for each node type's source file as it
is loaded, and these are saved when the graph is saved. If, on loading, the saved
checksum of a node does not match the current checksum, a warning is shown along with
the version numbers for both saved and current nodes.

**<font color="red">TODO: what happens with nodes with changing in/out counts between
versions, or nodes that can't be loaded?</font>**


### XFormType user interfaces 

Each XFormType object should be able to create a user interface for a node
of its type with its **createTab** method. This should create a tab object
of a subclass of **ui.tabs.Tab** defined in the xform's own module (however,
the generic **xforms.TabImage** is available for nodes which have no controls and a single
RGB image output). 

The subclass should implement **onNodeChanged**, which should update all the tab's
controls from the actual data stored in the node. Similarly, the tab should contain
code to update the node from the controls when they change (this can be achieved through
Qt's signals/slots mechanism: see the code for examples). If complex internal data changes
when controls are updated, the recalculate() method in the node type can be implemented.
When the node is changed from the tab in this way it should be commanded to perform().
The UI should be loaded from a Qt Designer file in the constructor by calling the superclass
constructor with an appropriate filename. Note that it will actually be loaded into
the **w** member - the tab widget - so controls should be accessed with **self.w.<name>**.

### Examples
A minimal example is **xforms/xformsink.py**, which simply displays an image. It is given in
its entirety below:
```python
import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage

# The node type itself, a subclass of XFormType with the @xformtype decorator which will
# calculate a checksum of this source file and automatically create the only instance which
# can exist of this class (it's a singleton).

@xformtype
class XformSink(XFormType):
    def __init__(self):
        # call superconstructor with the type name and version code
        super().__init__("sink","0.0.0")
        # set up a single input which takes an image of any type. The connector could have
        # a name in more complex node types, but here we just have an empty string.
        self.addInputConnector("","img")

    # this creates a tab when we want to control or view a node of this type. This uses
    # the built-in TabImage, which contains an OpenCV image viewer.
    def createTab(self,n):
        return TabImage(n)

    # actually perform a node's action, which happens when any of the nodes "upstream" are changed
    # and on loading.
    def perform(self,node):
        # get the input (index 0, our first and only input). That's all - we just store a reference
        # to the image in the node. The TabImage knows how to display nodes with "img" attributes,
        # and does the rest.
        node.img = node.getInput(0)
    def init(self,node):
        # initialise the node by setting its img to None.
        node.img = None
```


* A full example of a node type is given in **xforms/xformcontrast.py**, which has a single
control, displays as image and performs a simple contrast stretch. It is fully commented.
* The most complex node (from the point of view of user interface) is current **xformcrop.py**,
which allows a user to draw a crop rectangle on the image canvas; the cropped image is sent
to the output. This requires holding a **croprect** datum giving the crop rectangle position
and size, and handling the extra painting and mouse events via setting the appropriate hooks
in the canvas. See the code for details.
