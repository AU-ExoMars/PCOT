## @package xform
# The core model module, containing definitions of the xforms (nodes), the graph, and the
# type objects. The basic idea is that all XForms are the same, with the exception of additional data.
# Their behaviour is controlled by the XFormType object to which they link via their "type" member.


import copy
import hashlib
import inspect
import traceback
from collections import deque
from typing import List, Dict, Tuple, Any, ClassVar, Optional, TYPE_CHECKING

import json
import pyperclip
import uuid

import conntypes
import ui.tabs
from ui import graphscene
from inputs.inp import InputManager

if TYPE_CHECKING:
    import PyQt5.QtWidgets
    from macros import XFormMacro, MacroInstance

# ugly forward declarations so the type hints work
from pancamimage import ChannelMapping

## dictionary of name -> transformation type (XFormType)
allTypes = dict()


## custom exception which will cause an XForm to go into error
# state when thrown or set into setError().

class XFormException(Exception):
    ## @var code
    # A four-letter code for the message to display in the node's box
    # Codes:
    # DATA = bad data
    code: str

    ## @var message
    # a string message
    message: str

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


## Decorator for a transformation type. There is a singleton subclassed
# from this for each type. 
# This is a singleton decorator which, unusually, is not lazy, because we
# need the xforms to be registered at initialisation. Thus the class creation
# forces an instance to be created. We also use it to grab the source code
# and generate an MD5 checksum, so we are *sure* versions match.

# I'm suppressing a name warning because I prefer it like this!

# noinspection PyPep8Naming
class xformtype:
    def __init__(self, cls, *args, **kwargs):
        self._cls = cls
        # get the module so we can add an MD5 checksum of its source code to the type
        # data, for version matching info
        mod = inspect.getmodule(cls)
        src = inspect.getsource(mod).encode('utf-8')  # get the source
        self._instance = self._cls(*args, **kwargs)  # make the instance
        self._instance._md5 = hashlib.md5(src).hexdigest()  # add the checksum
        if self._instance.__doc__ is None:
            print("WARNING: no documentation for xform type '{}'".format(self._instance.name))

    def __call__(self):
        return self._instance


## This exception is thrown if a loaded node's MD5 checksum (from the node source when the 
# file was saved) disagrees with the node's current MD5: this means that the node's source
# code has changed, and the node is not guaranteed to work as it did when saved.

class BadVersionException(Exception):
    def __init__(self, n):
        self.message = "Node {} was saved with a different version of type {}".format(n.name, n.type.name)


## Superclass for a transformation type, defining how any XForm which links to it behaves.
class XFormType:
    ## @var name
    # name of the type
    name: str
    ## @var group
    # the palette group to which it belongs
    group: str
    ## @var ver
    # version number
    ver: str
    ## @var hasEnable
    # does it have an enable button?
    hasEnable: bool
    ## @var instances
    # all instances of this type in all graphs
    instances: List['XForm']

    ## @var inputConnectors
    # input connectors, a list of triples (name,connection type name, description)
    ## @var outputConnectors
    # output connectors, a list of triples (name,connection type name, description)

    # name is the name which appears in the graph view,
    # connection type name is 'any', 'imgrgb' etc.: the internal type name,
    # desc is used in the help window,

    inputConnectors: List[Tuple[str, str, str]]  # the inputs (name,connection type name,description)
    outputConnectors: List[Tuple[str, str, str]]  # the outputs (name,connection type name,description)

    ## @var autoserialise
    # tuple of autoserialisable attributes in each node of this type
    autoserialise: Tuple[str, ...]

    ## @var _md5
    # MD5 hash of source code (generated automatically)
    _md5: str

    ## constructor, takes name, groupname and version
    def __init__(self, name, group, ver):
        self.group = group
        self.name = name
        self.ver = ver
        self.instances = []
        # add to the global dictionary
        if name in allTypes:
            raise Exception("xform type name already in use: " + name)
        # register the type
        allTypes[name] = self
        # does this node have an "enabled" button? Change in subclass if reqd.
        self.hasEnable = False
        # this contains tuples of (name,typename). Images have typenames which
        # start with "img"
        self.inputConnectors = []
        # this has the same format, but here the output type
        # is the default type for that connection - when an xform is wired up
        # it may override this type. This means that when we wire up an
        # xform, a complicated little dance has to be done to determine the
        # actual output type and then disconnect any connections which are
        # no longer compatible.
        self.outputConnectors = []
        # The type may create additional attributes in the xform, which
        # can be listed here for automatic serialisation and deserialisation;
        # they must be simple Python data. This happens in addition to, and
        # before, the serialise() and deserialise() methods.
        self.autoserialise = ()  # tuple or list of attribute names

    ## call to remove node from instance list
    def remove(self, node):
        self.instances.remove(node)

    ## returns a checksum of the sourcecode for the module defining the type, MD5 hash, used
    # to check versions
    def md5(self):
        return self._md5

    ## run autoserialisation for a node
    def doAutoserialise(self, node):
        try:
            return {name: node.__dict__[name] for name in self.autoserialise}
        except KeyError as e:
            raise Exception("autoserialise value not in node {}: {}".format(self.name, e.args[0]))

    ## run autodeserialisation for a node
    def doAutodeserialise(self, node, ent):
        for name in self.autoserialise:
            # ignore key errors, for when we add data during development
            try:
                node.__dict__[name] = ent[name]
            except KeyError:
                pass

    ## create a new input connector; done in subclass constructor
    def addInputConnector(self, name, typename, desc=""):
        self.inputConnectors.append((name, typename, desc))

    ## create a new output connector; done in subclass constructor
    def addOutputConnector(self, name, typename, desc=""):
        self.outputConnectors.append((name, typename, desc))

    ## rename a node (the displayname, not the unique name).
    # Subclassed in connector nodes because they are messy.
    # even though we're only changing the display name
    def rename(self, node, name):
        node.displayName = name

    ## rename the type, used to rename a macro. Let's hope that
    # we don't reference types by name anywhere else.
    def renameType(self, newname):
        del allTypes[self.name]
        self.name = newname
        allTypes[newname] = self
        ui.mainwindow.MainUI.rebuildPalettes()
        ui.mainwindow.MainUI.rebuildAll()

    ## return all types
    @classmethod
    def all(cls):
        return allTypes

    # DOWN HERE ARE METHODS YOU MAY NEED TO OVERRIDE WHEN WRITING NODE TYPES

    # this is overriden if a node might change its output type depending on its
    # input types. It's called when an input connection is made or broken, and is followed
    # by a check on existing connections to those outputs which may then be broken if 
    # they are no longer compatible. It's called by XFormGraph.inputChanged(node).
    #
    # DO NOT modify the output type directly, use changeOutputType in the node. This
    # will tell the on-screen connector rect to update its brush. See xforms/xformcurve for
    # an example.
    def generateOutputTypes(self, node):
        pass

    ## override this - perform the actual action of the transformation, will generate outputs
    # in that object.
    def perform(self, xform):
        pass

    ## override this - initialise any data fields (often to None)
    def init(self, xform):
        pass

    ## maybe override - after control data has changed (either in a tab or by loading a file) it
    # may be necessary to recalculate internal data (e.g. lookup tables). Typically done when
    # internal data relies on a combination of controls. This
    # can be overridden to do that: it happens when a node is deserialised, when a node is created,
    # and should also be called in the tab's onNodeChanged() AFTER the controls are set
    # and BEFORE changing any status displays (see xformcurve for an example).
    def recalculate(self, xform):
        pass

    ## maybe override - return a dict of all values belonging to the node which should be saved.
    # This happens in addition to autoserialisation/deserialisation
    def serialise(self, xform):
        pass

    ## maybe override - given a dictionary, set the values in the node from the dictionary    
    # This happens in addition to autoserialisation/deserialisation
    def deserialise(self, xform, d):
        pass

    ## override this - create a tab connected to this xform, parented to a main window.
    # Might return none, if this xform doesn't have a meaningful UI.
    def createTab(self, xform, window):
        return None

    ## build the text element of the graph scene object for the node. By default, this
    # will just create static text, but can be overridden.
    @staticmethod
    def buildText(n):
        x, y = n.xy
        text = ui.graphscene.GText(n.rect, n.displayName, n)
        text.setPos(x + ui.graphscene.XTEXTOFFSET, y + ui.graphscene.YTEXTOFFSET + ui.graphscene.CONNECTORHEIGHT)
        return text


## serialise a connection (xform,i) into (xformName,i).
# Will only serialise connections into the set passed in. If None is passed
# in all connections are OK.
def serialiseConn(c, connSet):
    if c:
        x, i = c
        if (connSet is None) or (x in connSet):
            return x.name, i
    return None


## a piece of data sitting in a node's output, to be read by its input.
class Datum:
    ## @var tp
    # the data type
    tp: conntypes.Type
    ## @var val
    # the data value
    val: Any

    def __init__(self, t: conntypes.Type, v: Any):
        self.tp = t
        self.val = v

    def isImage(self):
        return conntypes.isImage(self.tp)


## an actual instance of a transformation, often called a "node".
class XForm:
    # type hints for attributes, here mainly as documentation

    ## @var type
    # the type of the node (this does the actual work)    
    type: XFormType

    ## @var savedver
    # the version number this node's type was saved with
    savedver: str

    ## @var inputs
    # list of tuples/none, each is the node we connect to and the output 
    # to which we are connected on that node
    inputs: List[Optional[Tuple['XForm', int]]]

    ## @var children
    # dictionary of nodes we output to and how many connections we have
    children: Dict['XForm', int]

    ## @var outputs
    # the actual output data from this node as a Datum object.
    outputs: List[Datum]

    ## @var outputTypes
    # the "overriding" output type (since an "img" output (say) may become
    # an "imgrgb") when the perform happens
    outputTypes: List[Optional[str]]

    ## @var inputTypes
    # the "overriding" input types (used in macros)
    inputTypes: List[Optional[str]]

    ## @var comment
    # a helpful comment
    comment: str

    ## @var name
    # the unique name of the node within the graph, which is internal only.
    # Note that in macros, corresponding nodes in the prototype graph
    # and instance graphs need to have the same name.
    # The name the user sees is displayName.
    name: str

    ## @var displayName
    # the name as displayed in the graph (and in the tab)
    displayName: str

    ## @var enabled
    # should this node perform?
    enabled: bool

    ## @var hasRun
    # has this node run already in this graph.perform cycle?
    hasRun: bool

    ## @var graph
    # the graph to which I belong
    graph: 'XFormGraph'

    ## @var savedmd5
    # only valid on nodes which are in the process of loading - stored
    # the MD5 value from the file
    savedmd5: Optional[str]

    ## @var instance
    # The macro instance if this is a macro - contains the instance graph
    # and some metadata
    instance: Optional['MacroInstance']

    # display data

    ## @var xy
    # the screen coordinates
    xy: Tuple[int, int]
    ## var w
    # screen width
    w: Optional[int]
    ## var h
    # screen height
    h: Optional[int]

    ## @var tabs
    # a list of open tabs
    tabs: List[ui.tabs.Tab]
    ## @var current
    # is this the currently selected node?
    current: bool
    ## @var rect
    # the main rectangle for the node in the scene
    rect: ['graphscene.GMainRect']
    ## @var inrects
    # input connector rectangles
    inrects: List[Optional['graphscene.GConnectRect']]
    ## @var outrects
    # output connector rectangles
    outrects: List[Optional['graphscene.GConnectRect']]
    ## @var helpwin
    # an open help window, or None
    helpwin: Optional['PyQt5.QtWidgets.QMainWindow']
    ## @var error
    # error state or None. See XFormException for codes.
    error: Optional[XFormException]

    ## constructor, takes type and displayname
    def __init__(self, tp, dispname):
        self.instance = None
        self.type = tp
        self.savedver = tp.ver
        self.savedmd5 = None
        # we keep a dict of those nodes which get inputs from us, and how many. We can't
        # keep the actual output connections easily, because they are one->many.
        self.children = {}
        self.comment = ""  # nodes can have comments
        # set the unique ID - unique to this graph, that is. This is rather
        # overkill, since it only needs to be unique within the graph and
        # indeed sometimes should be duplicated in other graphs (nodes in
        # macro instances should have the same name is the corresponding
        # node in the prototype)
        self.name = uuid.uuid4().hex
        # and the display name
        self.displayName = dispname
        # set up things which are dependent on the number of connectors,
        # which can change in macros. Initialise the inputs, though.
        self.inputs = [None] * len(tp.inputConnectors)
        self.connCountChanged()
        self.error = None

        # UI-DEPENDENT DATA DOWN HERE
        self.xy = (0, 0)  # this SHOULD be serialised

        # this stuff shouldn't be serialized
        # on-screen geometry, which should be set before we try to draw it
        self.w = None  # unset, will be set on draw
        self.h = None
        self.tabs = []  # no tabs open
        self.current = False
        self.rect = None  # the main GMainRect rectangle
        self.helpwin = None  # no help window
        self.enabled = True  # a lot of nodes won't use; see XFormType.
        self.hasRun = False  # used to mark a node as already having performed its stuff
        # all nodes have a channel mapping, because it's easier. See docs for that class.
        self.mapping = ChannelMapping()
        tp.instances.append(self)

    ## debugging
    def dumpInputs(self, t):
        print('--------', t)
        for i in range(0, len(self.inputs)):
            inp = self.inputs[i]
            if inp is not None:
                tp = self.inputTypes[i]
                print("{}: {}/{}/{}".format(i, inp[0], inp[1], tp))

    ## called to set an error state. Can either be called directly or invoked via
    # an exception. Takes an XFormException which may not necessarily have ever been raised.
    # Will result in a log message. After the perform has occurred, may also result in a
    # scene graph rebuild.
    def setError(self, ex: XFormException):
        self.error = ex
        ui.error(ex.message)

    ## called to clear the error state
    def clearError(self):
        self.error = None

    ## called when the connector count changes to set up the necessary
    # lists.
    def connCountChanged(self):
        # create unconnected connections. Connections are either None
        # or (Xform,index) tuples - the xform is the object to which we are
        # connected, the index is the index of the output connector on that xform for inputs,
        # or the input connector for outputs. This has to respect any existing connections,
        # otherwise editing becomes really painful.
        n = len(self.type.inputConnectors)
        if n > len(self.inputs):
            # there are more input connectors than inputs, add more to list
            self.inputs += [None] * (n - len(self.inputs))
        elif n < len(self.inputs):
            # there are fewer, truncate the inputs
            self.inputs = self.inputs[:n]
        # otherwise just leave it.

        # there is also a data output generated for each output by "perform", initially
        # these are None
        self.outputs = [None for _ in self.type.outputConnectors]
        # these are the overriding output types; none if we use the default
        # given by the type object (see the comment on outputConnectors
        # in XFormType)
        self.outputTypes = [None for _ in self.type.outputConnectors]
        self.inputTypes = [None for _ in self.type.inputConnectors]
        self.inrects = [None for _ in self.inputs]  # input connector GConnectRects
        self.outrects = [None for _ in self.outputs]  # output connector GConnectRects

    ## called when a node is deleted
    def onRemove(self):
        self.type.remove(self)

    ## set or clear the enabled field   
    def setEnabled(self, b):
        for x in self.tabs:
            x.setNodeEnabled(b)
        self.enabled = b
        self.graph.scene.selChanged()
        self.graph.changed(self)

    ## build a serialisable python dict of this node's values, including
    # only connections to/from the nodes in the selection (which may
    # be None if you want to serialize the whole set)
    def serialise(self, selection=None):
        d = {'xy': self.xy,
             'type': self.type.name,
             'displayName': self.displayName,
             'ins': [serialiseConn(c, selection) for c in self.inputs],
             'comment': self.comment,
             'outputTypes': self.outputTypes,
             'inputTypes': self.inputTypes,
             'md5': self.type.md5(),
             'ver': self.type.ver,
             'mapping': self.mapping.serialise()}
        if self.type.hasEnable:  # only save 'enabled' if the node uses it
            d['enabled'] = self.enabled

        # add autoserialised data
        d.update(self.type.doAutoserialise(self))
        # and run the additional serialisation method
        d2 = self.type.serialise(self)
        if d2 is not None:
            # avoids a type check problem
            d.update(d2 or {})
        return d

    ## deserialise a node from a python dict. Some entries already dealt with.
    def deserialise(self, d):
        self.xy = d['xy']
        self.comment = d['comment']
        self.outputTypes = d['outputTypes']
        self.inputTypes = d['inputTypes']
        self.savedver = d['ver']  # ver is version node was saved with
        self.savedmd5 = d['md5']  # and stash the MD5 we were saved with
        self.displayName = d['displayName']
        self.mapping = ChannelMapping.deserialise(d['mapping'])

        # some nodes don't have this, in which case we just set it
        # to true.
        if 'enabled' in d:
            self.enabled = d['enabled']
        else:
            self.enabled = True

        # autoserialised data
        self.type.doAutodeserialise(self, d)
        # run the additional deserialisation method
        self.type.deserialise(self, d)

    ## return the actual type of an output, taking account of overrides (node outputTypes). Note that
    # this returns the *connection* type, not the *datum* type stored in that connection.
    def getOutputType(self, i):
        if 0 <= i < len(self.outputs):
            if self.outputTypes[i] is None:
                return self.type.outputConnectors[i][1]
            else:
                return self.outputTypes[i]
        else:
            return None

    ## return the actual type of an input, taking account of overrides (node inputTypes). Again, this is
    # the *connection* type, not the *datum* type stored in that connection (or rather the output to
    # which it is connected)
    def getInputType(self, i):
        if 0 <= i < len(self.inputs):
            if self.inputTypes[i] is None:
                return self.type.inputConnectors[i][1]
            else:
                return self.inputTypes[i]
        else:
            return None

    ## is an output connected? This is a bit messy.
    def isOutputConnected(self, i):
        for outputnode in self.children:
            for inp in outputnode.inputs:
                if inp is not None:
                    inpnode, o = inp
                    if inpnode == self and o == i:
                        return True
        return False

    ## this should be used to change an output type in generateOutputTypes
    def changeOutputType(self, index, tp):
        self.outputTypes[index] = tp
        if self.outrects[index] is not None:
            #            print("MATCHING: {} becomes {}".format(index,type))
            self.outrects[index].typeChanged()

    ## this can be used in XFormType's generateOutputTypes if the polymorphism
    # is simply that some outputs should match the types of some inputs. The
    # input is a list of (out,in) tuples. Typical usage for a node with a single
    # input and output is matchOutputsToInputs([(0,0)])
    def matchOutputsToInputs(self, pairs):
        # reset all types - doing it this way in case we add extra outputs!
        self.outputTypes[:len(self.type.outputConnectors)] = [None for _ in self.type.outputConnectors]
        for o, i in pairs:
            if self.inputs[i] is not None:
                parent, pout = self.inputs[i]
                # the output type should be the same as the actual input (which is the
                # type of the output connected to that input)
                self.changeOutputType(o, parent.getOutputType(pout))
                if self.outrects[o] is not None:
                    self.outrects[o].typeChanged()

    ## return a debugging "name"
    def debugName(self):
        return "{}/{}/{}".format(self.type.name, self.name, self.displayName)

    ## debugging dump
    def dump(self):
        print("---DUMP of {}, geom {},{},{}x{}".format(self.debugName(),
                                                       self.xy[0], self.xy[1], self.w, self.h))
        print("  INPUTS:")
        for i in range(0, len(self.inputs)):
            c = self.inputs[i]
            if c:
                other, j = c
                print("    input {} <- {} {}".format(i, other.debugName(), j))
        print("   CHILDREN:")
        for k, v in self.children.items():
            print("    {} ({} connections)".format(k.name, v))
        s = "CONNECTED OUTPUTS: "
        for i in range(0, len(self.outputs)):
            if self.isOutputConnected(i):
                s += str(i) + " "
        print(s)

    ## cycle detector - is "other" one of my children? We do a breadth-first
    # search with a queue.
    def cycle(self, other):
        queue = deque()
        queue.append(self)
        while len(queue) > 0:
            p = queue.popleft()
            if p is other:
                return True
            for q in p.children:
                queue.append(q)
        return False

    ## connect an input to an output on another xform. Note that this doesn't
    # check compatibility; that's done in the UI.
    def connect(self, inputIdx, other, output, autoPerform=True):
        if 0 <= inputIdx < len(self.inputs) and self is not other:
            if 0 <= output < len(other.type.outputConnectors):
                if not self.cycle(other):  # this is a double check, the UI checks too.
                    self.inputs[inputIdx] = (other, output)
                    other.increaseChildCount(self)
                    if autoPerform:
                        other.graph.changed(other)  # perform the input node; the output should perform

    ## disconnect an input 
    def disconnect(self, inputIdx):
        if 0 <= inputIdx < len(self.inputs):
            if self.inputs[inputIdx] is not None:
                n, i = self.inputs[inputIdx]
                n.decreaseChildCount(self)
                self.inputs[inputIdx] = None
                self.graph.changed(self)  # run perform safely

    ## disconnect all inputs and outputs prior to removal
    def disconnectAll(self):
        for i in range(0, len(self.inputs)):
            self.disconnect(i)
        for n, v in self.children.items():
            # remove all inputs which reference this node
            for i in range(0, len(n.inputs)):
                if n.inputs[i] is not None:
                    if n.inputs[i][0] == self:
                        # do this directly, rather than with disconnect() both
                        # to avoid a concurrent modification and also because
                        # the child counts are irrelevant and don't need updating
                        n.inputs[i] = None

    ## change an output. This should be called by the type's perform method. Takes the type and datum.
    def setOutput(self, i:int, data:Datum):
        self.outputs[i] = data

    ## used in connection            
    def increaseChildCount(self, n):
        if n in self.children:
            self.children[n] += 1
        else:
            self.children[n] = 1

    ## used in disconnection
    def decreaseChildCount(self, n):
        if n in self.children:
            self.children[n] -= 1
            if self.children[n] == 0:
                del self.children[n]
        else:
            raise Exception("child count <0 in node {}, child {}".format(self.debugName(), n.debugName()))

    ## can this node run - are its inputs all set?
    def canRun(self):
        for inp in self.inputs:
            if inp is not None:
                out, index = inp
                if out.outputs[index] is None:
                    return False
        return True

    ## perform the transformation; delegated to the type object - recurses down the children.
    # Also tells any tab open on a node that its node has changed.
    # DO NOT CALL DIRECTLY - called either from itself or from performNodes.
    def perform(self):
        # used to stop perform being called out of context; it should
        # only be called inside the graph's perform.
        if not self.graph.performingGraph:
            raise Exception("Do not call perform directly on a node!")
        ui.msg("Performing {}".format(self.debugName()))
        try:
            # must clear this with prePerform on the graph, or nodes will
            # only run once!
            if self.hasRun:
                print("----Skipping {}, run already this action".format(self.debugName()))
            elif not self.canRun():
                print("----Skipping {}, it can't run (unset inputs)".format(self.debugName()))
            else:
                print("--------------------------------------Performing {}".format(self.debugName()))
                # first clear all outputs
                self.outputs = [None for _ in self.type.outputConnectors]
                # now run the node, catching any XFormException
                try:
                    self.type.perform(self)
                except XFormException as e:
                    # exception caught, set the error. Children will still run.
                    self.setError(e)
                self.hasRun = True
                # tell the tab that this node has changed
                for x in self.tabs:
                    x.onNodeChanged()
                    x.updateError()
                # run each child (could turn off child processing?)
                for n in self.children:
                    n.perform()
        except Exception as e:
            traceback.print_exc()
            ui.logXFormException(self, e)

    ## get the value of an input. Optional type; if passed in will check for that type and dereference the contents if
    # matched, else returning null.
    def getInput(self, i: int, tp=None) -> Datum:
        if self.inputs[i] is None:
            return None
        else:
            n, i = self.inputs[i]
            o = n.outputs[i]
            if tp is not None:
                if o.tp == tp:
                    return o.val
                else:
                    return None
            else:
                return o

    ## ensure connections are valid and break them if not
    def ensureConnectionsValid(self):
        for i in range(0, len(self.inputs)):
            inp = self.inputs[i]
            if inp is not None:
                n, idx = inp
                outtype = n.getOutputType(idx)
                intype = self.getInputType(i)
                if not conntypes.isCompatibleConnection(outtype, intype):
                    self.disconnect(i)

    ## rename a node - changes the displayname.
    def rename(self, name):
        # defer to type, because connector nodes have to rebuild all views.
        self.type.rename(self, name)


## a graph of transformation nodes
class XFormGraph:
    ## @var nodes
    # all my nodes
    nodes: List[XForm]

    ## @var scene
    # my graphical representation
    scene: Optional['graphscene.XFormGraphScene']

    ## @var isMacro
    # true if this is a macro prototype, will be false for instances
    isMacro: bool

    ## @var performingGraph    
    # true when I'm recursively performing my nodes. Avoids parallel
    # attempts to run a graph in different threads.
    performingGraph: bool

    ## @var nodeDict
    # dictionary of UUID to node, used to get instance nodes from prototypes
    nodeDict: Dict[str, XForm]

    ## @var proto
    # If this is a macro, the type object for the macro prototype (a singleton of
    # XFormMacro, itself a subclass of XFormType)
    proto: Optional['XFormMacro']

    ## @var autorun
    # should graphs be autorun
    autoRun: ClassVar[bool]
    autoRun = True

    ## @var inputs
    # The data inputs this system has
    inputMgr: InputManager

    ## @var captionType
    # integer indexing the caption type for canvases in this graph: see the box in MainWindow's ui for meanings.
    captionType: int

    ## constructor, takes whether the graph is a macro prototype or not
    def __init__(self, isMacro):
        # all the nodes
        self.proto = None
        self.nodes = []
        self.performingGraph = False
        self.scene = None  # the graph's scene is created by autoLayout
        self.isMacro = isMacro
        self.nodeDict = {}
        self.captionType = 0
        self.inputMgr = InputManager(self)

    ## construct a graphical representation for this graph
    def constructScene(self, doAutoLayout):
        self.scene = graphscene.XFormGraphScene(self, doAutoLayout)

    ## create a new node, passing in a type name.
    def create(self, typename):
        if typename in allTypes:
            tp = allTypes[typename]
            # display name is just the type name to start with.
            xform = XForm(tp, tp.name)
            self.nodes.append(xform)
            xform.graph = self
            tp.init(xform)  # run the init
            self.nodeDict[xform.name] = xform
            # force a recalc in those nodes that require it,
            # will generate internal data dependent on a combination
            # of all controls
            tp.recalculate(xform)
        else:
            ui.warn("Transformation type not found: " + typename)
            return self.create("dummy")
        return xform

    ## copy selected items to the clipboard. This copies a serialized
    # version, like that used for load/save.
    def copy(self, selection):
        # turn into JSON string
        s = json.dumps(self.serialise(selection))
        # copy to clipboard
        pyperclip.copy(s)

    ## paste the clipboard. This involves deserialising.
    # Returns a list of new nodes.
    def paste(self):
        # get string from clipboard
        s = pyperclip.paste()
        if len(s) > 0:
            try:
                d = json.loads(s)  # convert to dict
            except json.decoder.JSONDecodeError:
                raise Exception("Clipboard does not contain valid data")
            return self.deserialise(d, False)
        else:
            return []

    ## remove a node from the graph, and close any tab/window
    def remove(self, node):
        node.disconnectAll()
        for x in node.tabs:
            x.nodeDeleted()
        self.nodes.remove(node)
        del self.nodeDict[node.name]
        node.onRemove()

    ## debugging dump of entire graph
    def dump(self):
        for n in self.nodes:
            n.dump()

    ## we are about to perform some nodes due to a UI change.
    def prePerform(self):
        for n in self.nodes:
            n.clearError()
            n.hasRun = False

    ## Called when a control in a node has changed, and the node needs to rerun (as do all its children
    # recursively). If called on a normal graph, will perform the graph or a single node within it,
    # and all dependent nodes; called on a macro will do the same thing in instances, starting at the
    # counterpart node for that in the macro prototype.
    def changed(self, node=None):
        if self.autoRun:
            if self.inputMgr is not None:
                self.inputMgr.getAll()  # reread all inputs
            if self.isMacro:
                # distribute changes in macro prototype to instances.
                # what we do here is go through all instances of the macro. 
                # We copy the changed prototype to the instances, then run
                # the instances in the graphs which contain them (usually the
                # main graph).
                # This could be optimised to run only the relevant (changed) component
                # within the macro, but that's very hairy.

                for inst in self.proto.instances:
                    inst.instance.copyProto()
                    # "inst" is an XFormMacro node inside the graph which contains the macro,
                    # it is not the instance graph inside the "inst" node. Not sure how this
                    # will work if macros are inside macros!
                    # Anyway, inst.graph will be the main graph (for an non-nested macro).
                    # Self, however, is the macro prototype graph, because this method was called
                    # on an object inside that graph. We need to call performNodes() on the main graph
                    # to run the XFormMacro node inside that graph.
                    inst.graph.performNodes(inst)
            else:
                self.performNodes(node)
        else:
            ui.msg("Autorun not enabled")

    ## perform the entire graph, or all those nodes below a given node.
    # If the entire graph, performs a traversal from the root nodes.
    def performNodes(self, node=None):
        # if we are already running this method, exit. This
        # will be atomic because GIL. The use case here can
        # happen because turning a knob quickly will fire
        # off events quicker than we can run code. It seems.
        # It happens, anyway.
        if self.performingGraph:
            return

        self.prePerform()
        self.performingGraph = True
        if node is None:
            for n in self.nodes:
                # identify root nodes (no connected inputs).
                if all(i is None for i in n.inputs):
                    n.perform()
        else:
            node.perform()
        self.performingGraph = False
        # force a rebuild of the scene; error states may have changed.
        self.rebuildGraphics()

    def rebuildGraphics(self):
        if self.scene is not None:
            self.scene.rebuild()

    ## a node's input has changed, which may change the output types. If it does,
    # we need to check the output connections to see if they are still compatible.
    def inputChanged(self, node):
        # rebuild the types, perhaps replacing None (use the type default) with
        # a type name
        node.type.generateOutputTypes(node)
        # now check the children for nodes which connect to this one
        toDisconnect = []
        for child in node.children:
            for i in range(0, len(child.inputs)):
                if child.inputs[i] is not None:
                    parent, out = child.inputs[i]
                    if parent is node:
                        outtype = node.getOutputType(out)
                        intype = child.getInputType(i)
                        if not conntypes.isCompatibleConnection(outtype, intype):
                            toDisconnect.append((child, i))
        for child, i in toDisconnect:
            child.disconnect(i)

    ## serialise all nodes into a dict
    def serialise(self, items=None):
        # just serialise all the nodes into a dict, or those in a list.
        d = {}
        if items is None:
            items = self.nodes
        for n in items:
            d[n.name] = n.serialise(items)

        return d

    ## given a dictionary, build a graph based on it. Do not delete
    # any existing nodes unless asked and do not perform the nodes.
    # Returns a list of the new nodes. 
    def deserialise(self, d, deleteExistingNodes):
        if deleteExistingNodes:
            self.nodes = []
        # disambiguate nodes in the dict, to make sure they don't
        # have the same nodes as ones already in the graph
        d = self.disambiguate(d)
        newnodes = []
        # first pass - build the nodes
        for nodename, ent in d.items():
            n = self.create(ent['type'])
            newnodes.append(n)
            # remove the old name from the nodeDict
            del self.nodeDict[n.name]
            n.name = nodename  # override the default name (which is just a random UUID anyway)
            # and add the new name to the nodeDict
            self.nodeDict[nodename] = n
            n.deserialise(ent)  # will also deserialise type-specific data
            if n.type.md5() != n.savedmd5:
                ui.versionWarn(n)
            n.type.recalculate(n)  # recalculate internal data from controls
        # that done, fix up the references
        for nodename, ent in d.items():
            n = self.nodeDict[nodename]
            conns = ent['ins']
            for i in range(0, len(conns)):
                if conns[i] is not None:
                    oname, output = conns[i]  # tuples of name,index: see serialiseConn()
                    other = self.nodeDict[oname]
                    n.connect(i, other, output, False)  # don't automatically perform
        # and finally match output types
        for n in newnodes:
            n.type.generateOutputTypes(n)
        return newnodes

    ## a really ugly thing for just scanning through and returning true if a node
    # of a given name exists. The *correct* thing to do would be have a dict of
    # nodes by name, of course. But this is plenty fast enough.
    def nodeExists(self, name):
        for n in self.nodes:
            if n.name == name:
                return True
        return False

    ## change the names of nodes in the dict which have the same names as
    # nodes in the existing graph. Returns a new dict.
    def disambiguate(self, d):
        # we do this by creating a new dict. If there are no nodes in
        # the current graph we can just skip it.
        if len(self.nodes) == 0:
            return d

        newd = {}  # new dict to be returned
        renamed = {}  # dict of renamed nodes: oldname->newname
        newnames = []  # list of new names (values in the above dict)

        for k, v in d.items():
            oldname = k
            # while there's still a node in the actual graph that's the same,
            # or we've already renamed something to that
            while self.nodeExists(k) or k in newnames:
                k = uuid.uuid4().hex  # generate a UUID
            renamed[oldname] = k
            newnames.append(k)
            # this avoids modification of the clipboard objects, which is disastrous(?)
            newd[k] = copy.deepcopy(v)

        # first pass done, now we need to rename all connections;
        # again, scan the entire new dictionary

        for k, v in newd.items():
            # scan all inputs; done by index
            conns = v['ins']
            for i in range(0, len(conns)):
                if conns[i] is not None:
                    oname, output = conns[i]
                    if oname in renamed:
                        conns[i] = (renamed[oname], output)
            v['ins'] = conns
            # and pass back the new, disambiguated dict
        return newd

    ## ensure all connections are valid (i.e. in/out types are compatible)
    # and break those which aren't
    def ensureConnectionsValid(self):
        for n in self.nodes:
            n.ensureConnectionsValid()
