"""The core model module, containing definitions of the xforms (nodes), the graph, and the
type objects. The basic idea is that all XForms are the same, with the exception of additional data.
Their behaviour is controlled by the XFormType object to which they link via their "type" member.
"""
import base64
import copy
import hashlib
import inspect
import time
import traceback
from collections import deque
from io import BytesIO
from typing import List, Dict, Tuple, Any, ClassVar, Optional, TYPE_CHECKING, Callable

import json

import cv2
import numpy as np
import pyperclip
import uuid

import pcot.conntypes as conntypes
import pcot.macros
from pcot.conntypes import Datum
import pcot.ui as ui
from pcot import inputs
from pcot.ui import graphscene
from pcot.inputs.inp import InputManager
from pcot.ui.canvas import Canvas
from pcot.utils import archive

if TYPE_CHECKING:
    import PyQt5.QtWidgets
    from macros import XFormMacro, MacroInstance

# ugly forward declarations so the type hints work
from pcot.pancamimage import ChannelMapping


## dictionary of name -> transformation type (XFormType)
allTypes = dict()


class XFormException(Exception):
    """custom exception which will cause an XForm to go into error
    state when thrown or set into setError().
    """
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


_xformctors = []            # list of (xformtype,classobject,args,kwargs,md5) tuples


def createXFormTypeInstances():
    for xft, cls, args, kwargs, md5 in _xformctors:
        i = cls(*args, *kwargs)
        xft._instance = i
        if i.name in allTypes:
            raise Exception("xform type name already in use: " + i.name)
        allTypes[i.name] = i
        i._md5 = md5
        if i.__doc__ is None:
            print("WARNING: no documentation for xform type '{}'".format(i.name))


# I'm suppressing a name warning because I prefer it like this!

# noinspection PyPep8Naming
class xformtype:
    """Decorator for a transformation type. There is a singleton subclassed
    from this for each type.
    This is a singleton decorator which, unusually, is not lazy, because we
    need the xforms to be registered at initialisation. Thus the class creation
    forces an instance to be created. We also use it to grab the source code
    and generate an MD5 checksum, so we are *sure* versions match.

    Well, it's SORT of lazy because it just adds data to a list which createXFormTypeInstances iterates over later,
    once everything is up.
    """

    def __init__(self, cls, *args, **kwargs):
        self._cls = cls
        # get the module so we can add an MD5 checksum of its source code to the type
        # data, for version matching info
        mod = inspect.getmodule(cls)
        src = inspect.getsource(mod).encode('utf-8')  # get the source

        # we don't create the instance - that's postponed until later to avoid some circular import
        # problems when expr is initialised (it's quite difficult to run the user function hooks this
        # early). We add the required info to a list, which createXFormTypeInstances() runs through later.

        md5 = hashlib.md5(src).hexdigest()  # add the checksum
        _xformctors.append((self, cls, args, kwargs, md5))

    def __call__(self):
        return self._instance



class BadVersionException(Exception):
    """This exception is thrown if a loaded node's MD5 checksum (from the node source when the
    file was saved) disagrees with the node's current MD5: this means that the node's source
    code has changed, and the node is not guaranteed to work as it did when saved.
    """

    def __init__(self, n):
        self.message = "Node {} was saved with a different version of type {}".format(n.name, n.type.name)


class XFormType:
    """Superclass for a transformation type, defining how any XForm which links to it behaves."""
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

    def __init__(self, name, group, ver):
        """constructor, takes name, groupname and version"""
        self.group = group
        self.name = name
        self.ver = ver
        self.instances = []
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

    def remove(self, node):
        """call to remove node from instance list"""
        self.instances.remove(node)

    def md5(self):
        """returns a checksum of the sourcecode for the module defining the type, MD5 hash, used to check versions"""
        return self._md5

    def doAutoserialise(self, node):
        """run autoserialisation for a node"""
        try:
            return {name: node.__dict__[name] for name in self.autoserialise}
        except KeyError as e:
            raise Exception("autoserialise value not in node {}: {}".format(self.name, e.args[0]))

    def doAutodeserialise(self, node, ent):
        """run autodeserialisation for a node"""
        for name in self.autoserialise:
            # ignore key errors, for when we add data during development
            try:
                node.__dict__[name] = ent[name]
            except KeyError:
                pass

    def addInputConnector(self, name, typename, desc=""):
        """create a new input connector; done in subclass constructor"""
        self.inputConnectors.append((name, typename, desc))

    def addOutputConnector(self, name, typename, desc=""):
        """create a new output connector; done in subclass constructor"""
        self.outputConnectors.append((name, typename, desc))

    def rename(self, node, name):
        """rename a node (the displayname, not the unique name).
        Subclassed in connector nodes because they are messy.
        even though we're only changing the display name
        """
        node.displayName = name

    def delType(self):
        """delete a type! Used to delete old macros"""
        del allTypes[self.name]

    def renameType(self, newname):
        """rename the type, used to rename a macro.
        Let's hope that we don't reference types by name anywhere else.
        """
        del allTypes[self.name]
        self.name = newname
        allTypes[newname] = self
        ui.mainwindow.MainUI.rebuildPalettes()
        ui.mainwindow.MainUI.rebuildAll()

    def cycleCheck(self, g):
        """does this type's prototype graph (if it is a macro) contain a macro
        whose graph is g? False by default."""
        return False

    @classmethod
    def all(cls):
        """return all types"""
        return allTypes

    # DOWN HERE ARE METHODS YOU MAY NEED TO OVERRIDE WHEN WRITING NODE TYPES

    def generateOutputTypes(self, node):
        """this is overriden if a node might change its output type depending on its input types.
            It's called when an input connection is made or broken, and is followed
            by a check on existing connections to those outputs which may then be broken if
            they are no longer compatible. It's called by XFormGraph.inputChanged(node).
            DO NOT modify the output type directly, use changeOutputType in the node. This
            will tell the on-screen connector rect to update its brush.
            """
        pass

    def perform(self, xform):
        """override this - perform the actual action of the transformation, will generate outputs in that object."""
        pass

    def uichange(self, xform):
        """Respond to changes in a tab. If autorun is not set, this alone is run on the changed node. If autorun is
        set, the perform() runs immediately after it and the run recurses down the children. For some fast nodes,
        it's fine to have this call perform() if there are important UI changes (such as ROIs). It will run twice, but
        that's OK.
        """
        pass

    def init(self, xform):
        """override this - initialise any data fields (often to None)"""
        pass

    def recalculate(self, xform):
        """maybe override to recalculate internal data
            after control data has changed (either in a tab or by loading a file) it
            may be necessary to recalculate internal data (e.g. lookup tables). Typically done when
            internal data relies on a combination of controls. This
            can be overridden to do that: it happens when a node is deserialised, when a node is created,
            and should also be called in the tab's onNodeChanged() AFTER the controls are set
            and BEFORE changing any status displays.
            """
        pass

    def serialise(self, xform):
        """maybe override - return a dict of all values belonging to the node which should be saved.
            This happens in addition to autoserialisation/deserialisation
        """
        pass

    def deserialise(self, xform, d):
        """maybe override - given a dictionary, set the values in the node from the dictionary
            This happens in addition to autoserialisation/deserialisation
        """
        pass

    def createTab(self, xform, window):
        """usually override this - create a tab connected to this xform, parented to a main window.
            Might return none, if this xform doesn't have a meaningful UI.
            """

        return None

    @staticmethod
    def buildText(n):
        """build the text element of the graph scene object for the node.
        By default, this will just create static text, but can be overridden.
        """
        x, y = n.xy
        text = graphscene.GText(n.rect, n.displayName, n)
        text.setPos(x + graphscene.XTEXTOFFSET, y + graphscene.YTEXTOFFSET + graphscene.CONNECTORHEIGHT)
        return text


def serialiseConn(c, connSet):
    """serialise a connection (xform,i) into (xformName,i).
    Will only serialise connections into the set passed in. If None is passed
    in all connections are OK."""
    if c:
        x, i = c
        if (connSet is None) or (x in connSet):
            return x.name, i
    return None





class BadTypeException(Exception):
    """Raised when XForm.getOutput() asks for an incorrect type"""

    def __init__(self, i):
        super().__init__("incorrect output type requested, index {}".format(i))


class XForm:
    """an actual instance of a transformation, often called a "node"."""

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
    outputs: List[Optional[Datum]]

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
    tabs: List['pcot.ui.tabs.Tab']
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
    ## @var rectText
    # extra text displayed (if there's no error)
    rectText: Optional[str]
    ## @var runTime
    # the time this node took to run in the last call to performNodes
    runTime: float

    def __init__(self, tp, dispname):
        """constructor, takes type and displayname"""
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
        self.rectText = None
        self.runTime = 0

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
        Canvas.initPersistData(self)

    def dumpInputs(self, t):
        """debugging"""
        print('--------', t)
        for i in range(0, len(self.inputs)):
            inp = self.inputs[i]
            if inp is not None:
                tp = self.inputTypes[i]
                print("{}: {}/{}/{}".format(i, inp[0], inp[1], tp))

    def setError(self, ex: XFormException):
        """called to set an error state. Can either be called directly or invoked via an exception.
        Takes an XFormException which may not necessarily have ever been raised.
        After the perform has occurred, may also result in a scene graph rebuild.
        """
        self.error = ex
        # ui.error(ex.message)           # the beeps are really annoying...

    def setRectText(self, t):
        """set the rect text: extra text displayed along with the name and any error"""
        self.rectText = t

    def clearErrorAndRectText(self):
        """clear the error state and rect text"""
        self.error = None
        self.rectText = None

    def clearOutputs(self):
        """clear all the node's outputs, required on all nodes before we run the graph
            (it's how we check a node can run - are all its input nodes' outputs set?)
            """
        self.outputs = [None for _ in self.type.outputConnectors]

    def connCountChanged(self):
        """called when the connector count changes to set up the necessary lists."""
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
        self.clearOutputs()
        # these are the overriding output types; none if we use the default
        # given by the type object (see the comment on outputConnectors
        # in XFormType)
        self.outputTypes = [None for _ in self.type.outputConnectors]
        self.inputTypes = [None for _ in self.type.inputConnectors]
        self.inrects = [None for _ in self.inputs]  # input connector GConnectRects
        self.outrects = [None for _ in self.outputs]  # output connector GConnectRects

    def onRemove(self):
        """called when a node is deleted"""
        self.type.remove(self)

    def setEnabled(self, b):
        """set or clear the enabled field"""
        for x in self.tabs:
            x.setNodeEnabled(b)
        self.enabled = b
        self.graph.scene.selChanged()
        self.graph.changed(self)

    def serialise(self, selection=None):
        """build a serialisable python dict of this node's values
        including only connections to/from the nodes in the selection (which may
        be None if you want to serialize the whole set)
        """
        d = {'xy': self.xy,
             'type': self.type.name,
             'displayName': self.displayName,
             'ins': [serialiseConn(c, selection) for c in self.inputs],
             'comment': self.comment,
             'outputTypes': [None if x is None else x.name for x in self.outputTypes],
             'inputTypes': [None if x is None else x.name for x in self.inputTypes],
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
        Canvas.serialise(self, d)
        return d

    def deserialise(self, d):
        """deserialise a node from a python dict.
        Some entries have already been already dealt with."""
        self.xy = d['xy']
        self.comment = d['comment']
        # these are the overriding types - if the value is None, use the xformtype's value, else use the one here.
        self.outputTypes = [None if x is None else conntypes.deserialise(x) for x in d['outputTypes']]
        self.inputTypes = [None if x is None else conntypes.deserialise(x) for x in d['inputTypes']]
        self.savedver = d['ver']  # ver is version node was saved with
        self.savedmd5 = d['md5']  # and stash the MD5 we were saved with
        self.displayName = d['displayName']
        self.mapping = ChannelMapping.deserialise(d['mapping'])
        Canvas.deserialise(self, d)

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

    def getOutputType(self, i):
        """return the actual type of an output, taking account of overrides (node outputTypes).
        Note that this returns the *connection* type, not the *datum* type stored in that connection.
        """
        try:
            if 0 <= i < len(self.outputs):
                if self.outputTypes[i] is None:
                    return self.type.outputConnectors[i][1]
                else:
                    return self.outputTypes[i]
            else:
                return None
        except IndexError:
            return None

    def getInputType(self, i):
        """return the actual type of an input, taking account of overrides (node inputTypes).
            Again, this is the *connection* type, not the *datum* type stored in that connection
            (or rather the output to which it is connected)
            """
        try:
            if 0 <= i < len(self.inputs):
                if self.inputTypes[i] is None:
                    return self.type.inputConnectors[i][1]
                else:
                    return self.inputTypes[i]
            else:
                return None
        except IndexError:
            return None

    def getOutput(self, i, tp=None):
        """get an output, raising an exception if the type is incorrect or the index is output range
        used in external code; compare with Datum.get() which doesn't raise.
        """
        d = self.outputs[i]  # may raise IndexError
        if d is None:
            return None
        elif tp is None or d.tp == tp or tp == conntypes.IMG and d.isImage():
            return d.val
        else:
            raise BadTypeException(i)

    def isOutputConnected(self, i):
        """is an output connected?"""
        # This is a bit messy.
        for outputnode in self.children:
            for inp in outputnode.inputs:
                if inp is not None:
                    inpnode, o = inp
                    if inpnode == self and o == i:
                        return True
        return False

    def changeOutputType(self, index, tp):
        """this should be used to change an output type in generateOutputTypes"""
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

    def debugName(self):
        """return a debugging "name"""
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

    def cycle(self, other):
        """cycle detector - is "other" one of my children? We do a breadth-first search with a queue."""
        queue = deque()
        queue.append(self)
        while len(queue) > 0:
            p = queue.popleft()
            if p is other:
                return True
            for q in p.children:
                queue.append(q)
        return False

    def connect(self, inputIdx, other, output, autoPerform=True):
        """connect an input to an output on another xform.
            Note that this doesn't check compatibility; that's done in the UI.
            """
        if 0 <= inputIdx < len(self.inputs) and self is not other:
            if 0 <= output < len(other.type.outputConnectors):
                if not self.cycle(other):  # this is a double check, the UI checks too.
                    self.inputs[inputIdx] = (other, output)
                    other.increaseChildCount(self)
                    if autoPerform:
                        other.graph.changed(other)  # perform the input node; the output should perform

    def disconnect(self, inputIdx):
        """disconnect an input"""
        if 0 <= inputIdx < len(self.inputs):
            if self.inputs[inputIdx] is not None:
                n, i = self.inputs[inputIdx]
                n.decreaseChildCount(self)
                self.inputs[inputIdx] = None
                self.graph.changed(self)  # run perform safely

    def disconnectAll(self):
        """disconnect all inputs and outputs prior to removal"""
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

    def setOutput(self, i: int, data: Datum):
        """change an output. This should be called by the type's perform method. Takes the type and datum."""
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

    def uichange(self):
        self.type.uichange(self)

    def updateTabs(self):
        for x in self.tabs:
            x.onNodeChanged()
            x.updateError()

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
                self.clearOutputs()
                # now run the node, catching any XFormException
                try:
                    st = time.perf_counter()
                    self.uichange()
                    self.type.perform(self)
                    self.runTime = time.perf_counter() - st
                except XFormException as e:
                    # exception caught, set the error. Children will still run.
                    self.setError(e)
                self.hasRun = True
                # tell the tab that this node has changed
                self.updateTabs()
                # run each child (could turn off child processing?)
                for n in self.children:
                    n.perform()
        except Exception as e:
            traceback.print_exc()
            ui.logXFormException(self, e)

    def getInput(self, i: int, tp=None) -> Optional[Datum]:
        """get the value of an input.
            Optional type; if passed in will check for that type and dereference the contents if
            matched, else returning null.
            """
        if self.inputs[i] is None:
            return None
        else:
            n, i = self.inputs[i]
            o = n.outputs[i]
            if tp is not None and o is not None:
                if o.tp == tp:
                    return o.val
                else:
                    return None
            else:
                return o

    def ensureConnectionsValid(self):
        """ensure connections are valid and break them if not"""
        for i in range(0, len(self.inputs)):
            inp = self.inputs[i]
            if inp is not None:
                n, idx = inp
                outtype = n.getOutputType(idx)
                intype = self.getInputType(i)
                if not conntypes.isCompatibleConnection(outtype, intype):
                    self.disconnect(i)

    def rename(self, name):
        """rename a node - changes the displayname."""
        # defer to type, because connector nodes have to rebuild all views.
        self.type.rename(self, name)

    def __str__(self):
        return "XForm-{}-{}-{}".format(id(self), self.displayName, self.type.name)


class XFormGraph:
    """a graph of transformation nodes: this is the primary PCOT document type"""
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

    ## @var doc
    # the document of which I am a part, whether as the top-level graph or a macro.
    doc: 'Document'

    def __init__(self, doc, isMacro):
        """constructor, takes whether the graph is a macro prototype or not"""
        self.proto = None
        self.doc = doc
        self.nodes = []
        self.performingGraph = False
        self.scene = None  # the graph's scene is created by autoLayout
        self.isMacro = isMacro
        self.nodeDict = {}

    def constructScene(self, doAutoLayout):
        """construct a graphical representation for this graph"""
        self.scene = graphscene.XFormGraphScene(self, doAutoLayout)

    def create(self, typename):
        """create a new node, passing in a type name. We look in both the 'global' dictionary,
        allTypes,  but also the macros for this document"""
        if typename in allTypes:
            tp = allTypes[typename]
        elif typename in self.doc.macros:
            tp = self.doc.macros[typename]
        else:
            ui.warn("Transformation type not found: " + typename)
            return self.create("dummy")

        # first, try to make sure we aren't creating a macro inside itself
        if tp.cycleCheck(self):
            raise XFormException('TYPE', "Cannot create a macro which contains itself")

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
        return xform

    def copy(self, selection):
        """copy selected items to the clipboard.
            This copies a serialized version, like that used for load/save - but it's hairier than it might seem because
            there might be numpy data in there. So we build a ZIP archive of the JSON and numpy arrays,
            convert that to b64 and store that string. Ugh.
        """
        # turn into binary data
        with archive.MemoryArchive() as a:
            a.writeJson("clipboard", self.serialise(selection))
        # make sure we have closed the archive (the outdent here will do it)

        # copy to clipboard as a string; this is ugly and may be slow. Particularly if we
        # end up serialising lots of numpy data! However, it is still compressed with DEFLATE.
        s = base64.b64encode(a.get().getvalue()).decode()  # get memory from bytesio, encode as b64, convert to string.
        pyperclip.copy(s)

    def paste(self):
        """paste the clipboard.
        This involves deserialising.
        Returns a list of new nodes.
        """
        # get data from clipboard as a b64 encoded string
        s = pyperclip.paste()
        if len(s) > 0:
            try:
                # decode the b64 string into bytes
                s = base64.b64decode(s)
                # make a memory archive out of these bytes and read it
                with archive.MemoryArchive(BytesIO(s)) as a:
                    d = a.readJson("clipboard")
            except json.decoder.JSONDecodeError:
                raise Exception("Clipboard does not contain valid data")
            return self.deserialise(d, False)
        else:
            return []

    def remove(self, node):
        """remove a node from the graph, and close any tab/window"""
        if node in self.nodes:
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

    ## handy visitor method
    def visit(self, root: Optional[XForm], fn: Callable[[XForm], None]):
        fn(root)
        for n in root.children:
            self.visit(n, fn)

    ## we are about to perform some nodes due to a UI change, so reset errors, hasRun flag, and outputs
    # of the descendants of the node we are running (or all nodes if we are running the entire graph)
    def prePerform(self, root: Optional[XForm]):
        nodeset = set()
        if root is not None:
            self.visit(root, lambda x: nodeset.add(x))
        else:
            nodeset = set(self.nodes)
        for n in nodeset:
            n.clearErrorAndRectText()
            n.clearOutputs()
            n.hasRun = False
        for n in self.nodes:
            n.runTime = None

    def changed(self, node=None, runAll=False, uiOnly=False):
        """Called when a control in a node has changed, and the node needs to rerun (as do all its children recursively).
        If called on a normal graph, will perform the graph or a single node within it,
        and all dependent nodes; called on a macro will do the same thing in instances, starting at the
        counterpart node for that in the macro prototype.
        """

        if (not uiOnly) and (XFormGraph.autoRun or runAll):
            # reread all inputs for my document (should cache!)
            self.doc.inputMgr.readAll()

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

                # and rebuild graphics in the prototype
                self.rebuildGraphics()
            else:
                self.performNodes(node)
        elif node is not None:
            # this always happens when an individual node is changed, even if autorun is off. Note that it happens
            # to every node before perform() when autorun is on (hence the elif below).
            node.uichange()
            # and update tabs.
            node.updateTabs()
            ui.msg("Autorun not enabled")

        # make sure the caption in any attached window is correct.
        for xx in ui.mainwindow.MainUI.windows:
            if xx.graph == self:
                xx.setCaption(self.doc.settings.captionType)

    def performNodes(self, node=None):
        """perform the entire graph, or all those nodes below a given node.
            If the entire graph, performs a traversal from the root nodes.
            """
        # if we are already running this method, exit. This
        # will be atomic because GIL. The use case here can
        # happen because turning a knob quickly will fire
        # off events quicker than we can run code. It seems.
        # It happens, anyway.
        if self.performingGraph:
            return

        self.prePerform(node)
        self.performingGraph = True
        if node is None:
            for n in self.nodes:
                # identify root nodes (no connected inputs).
                if all(i is None for i in n.inputs):
                    n.perform()
        else:
            node.perform()
        self.performingGraph = False

        self.showPerformance()

        # force a rebuild of the scene; error states may have changed.
        self.rebuildGraphics()

    def showPerformance(self):
        """show how long each node took to run"""
        tot = 0
        for n in sorted([x for x in self.nodes if x.runTime is not None], key=lambda x: x.runTime):
            tot = tot + n.runTime
            print("{:<10.3f} {} ".format(n.runTime, n.displayName))
        print("{:<10.3f} TOTAL".format(tot))

    def rebuildGraphics(self):
        """rebuild all graphics elements if a scene is present"""
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

    def serialise(self, items=None):
        """serialise all nodes into a dict"""
        # just serialise all the nodes into a dict, or those in a list.
        d = {}
        if items is None:
            items = self.nodes
        for n in items:
            d[n.name] = n.serialise(items)

        return d

    def deserialise(self, d, deleteExistingNodes):
        """given a dictionary, add nodes stored in it in serialized form.
            Do not delete any existing nodes unless asked and do not perform the nodes.
            Returns a list of the new nodes.
            """
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

    def ensureConnectionsValid(self):
        """ensure all connections are valid (i.e. in/out types are compatible)
            and break those which aren't
            """
        for n in self.nodes:
            n.ensureConnectionsValid()


class XFormROIType(XFormType):
    """Class for handling ROI xform types, does most of the heavy lifting of the node's perform
    function. The actual ROIs are dealt with in pancamimage"""

    # constants enumerating the outputs
    OUT_IMG = 0
    OUT_ANNOT = 1
    OUT_ROI = 2

    IN_IMG = 0
    IN_ANNOT = 1

    def __init__(self, name, group, ver):
        super().__init__(name, group, ver)
        self.addInputConnector("input", conntypes.IMG)
        self.addInputConnector("ann", conntypes.IMGRGB, "used as base for annotated image")
        self.addOutputConnector("img", conntypes.IMG, "image with ROI")  # image+roi
        self.addOutputConnector("ann", conntypes.IMGRGB,
                                "image as RGB with ROI, with added annotations around ROI")  # annotated image
        self.addOutputConnector("roi", conntypes.ROI, "the region of interest")

        self.autoserialise = ('caption', 'captiontop', 'fontsize', 'fontline', 'colour')

    def setProps(self, node, img):
        """Set properties in the node and ROI attached to the node. Assumes img is a valid
        imagecube, and node.roi is the ROI"""
        pass

    def uichange(self, n):
        self.perform(n)

    def perform(self, node):
        img = node.getInput(self.IN_IMG, conntypes.IMG)
        inAnnot = node.getInput(self.IN_ANNOT, conntypes.IMG)
        # label the ROI
        node.roi.label = node.caption
        node.setRectText(node.caption)

        if img is None:
            # no image
            node.setOutput(self.OUT_IMG, None)
            node.setOutput(self.OUT_ANNOT, None if inAnnot is None else Datum(conntypes.IMGRGB, inAnnot))
            node.setOutput(self.OUT_ROI, None)
        else:
            self.setProps(node, img)
            # copy image and append ROI to it
            img = img.copy()
            img.rois.append(node.roi)
            # set mapping from node
            img.setMapping(node.mapping)
            # create a new RGB image or use the input one
            rgb = img.rgbImage() if inAnnot is None else inAnnot.copy()
            # now make an annotated image by drawing ROIS on the RGB image; ours should be a bit different
            # if showROIs (handled by canvas) is true, draw all ROIs, otherwise only draw one.
            img.drawROIs(rgb.img, onlyROI=None if node.showROIs else node.roi)
            rgb.rois = img.rois  # with same ROI list as unannotated image
            node.rgbImage = rgb  # the RGB image shown in the canvas (using the "premapping" idea)
            node.setOutput(self.OUT_ANNOT, Datum(conntypes.IMG, rgb))
            node.img = img
            # output the ROI - note that this is NOT a copy!
            node.setOutput(self.OUT_ROI, Datum(conntypes.ROI, node.roi))

            if node.isOutputConnected(self.OUT_IMG):
                node.setOutput(self.OUT_IMG, Datum(conntypes.IMG, node.img))  # output image and ROI
