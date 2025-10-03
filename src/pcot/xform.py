"""The core model module, containing definitions of the xforms (nodes), the graph, and the
type objects. The basic idea is that all XForms are the same, with the exception of additional data.
Their behaviour is controlled by the XFormType object to which they link via their "type" member.
"""
import base64
import copy
import hashlib
import inspect
import json
import time
import traceback
import logging
import sys
import uuid
from collections import deque
from html import escape
from io import BytesIO
from typing import List, Dict, Tuple, ClassVar, Optional, TYPE_CHECKING, Callable, Union, Any, Set

import pyperclip

import pcot.macros
import pcot.ui as ui
from pcot import datum
from pcot.datum import Datum

from pcot.sources import nullSourceSet, MultiBandSource
from pcot.ui import graphscene
from pcot.ui.canvas import Canvas
from pcot.ui.tabs import Tab
from pcot.utils import archive

if TYPE_CHECKING:
    from macros import XFormMacro, MacroInstance

from pcot.imagecube import ChannelMapping


logger = logging.getLogger(__name__)

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


_xformctors = []  # list of (xformtype,classobject,args,kwargs,md5) tuples


def createXFormTypeInstances():
    # clear allTypes just in case we call this multiple times (as we do from tests)
    global allTypes
    allTypes = {}
    for xft, cls, args, kwargs, md5 in _xformctors:
        i = cls(*args, *kwargs)
        xft._instance = i
        if i.name in allTypes:
            raise Exception("xform type name already in use: " + i.name)
        allTypes[i.name] = i
        i._md5 = md5
        if i.__doc__ is None:
            logger.warning(f"WARNING: no documentation for xform type '{i.name}'")


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

        # can't get source when inside pyinstaller etc.
        if not (getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')):
            src = inspect.getsource(mod).encode('utf-8')  # get the source
        else:
            src = ''.encode('utf-8')

        # we don't create the instance - that's postponed until later to avoid some circular import
        # problems when expr is initialised (it's quite difficult to run the user function hooks this
        # early). We add the required info to a list, which createXFormTypeInstances() runs through later.

        md5 = hashlib.md5(src).hexdigest()  # add the checksum
        _xformctors.append((self, cls, args, kwargs, md5))
        logger.debug(f"Appending instance for {str(cls)}")

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
    # name of the type
    name: str
    # the palette group to which it belongs
    group: str
    # version number
    ver: str
    # does it have an enable button?
    hasEnable: bool
    # an open help window, or None
    helpwin: Optional['PyQt5.QtWidgets.QMainWindow']
    inputConnectors: List[Tuple[str, 'Type', str]]  # the inputs (name,connection type,description)
    outputConnectors: List[Tuple[str, 'Type', str]]  # the outputs (name,connection type,description)
    # tuple of autoserialisable attributes in each node of this type
    # These are either strings or tuples, in which case the first element is the name and the second
    # is a default value used when legacy files are loaded which doesn't have that value.
    autoserialise: Tuple[Union[str, Tuple[str, Any]], ...]
    # MD5 hash of source code (generated automatically)
    _md5: str
    # minimum width of node on screen
    minwidth: int
    # can we resize this node by dragging a corner?
    resizable: bool
    # should nodes of this type show their performed count? It's pointless for comments, for example,
    # and messes up their resizing.
    showPerformedCount: bool
    # callable to set parameters for QGraphicsRectItem; may be null
    setRectParams: Optional[Callable[['QGraphicsRectItem'], None]]
    # sometimes a node's name gets changed - this happened with "gradient" being changed to "colourmap".
    # When that happens we want to rename the node's type, and make sure the displayName is handled
    # correctly. This is a set of the old names
    oldNames: Set[str]

    def __init__(self, name, group, ver, hasEnable=False, startEnabled=True):
        """
        constructor, takes name, groupname and version.
        Optionally:
            hasEnable - the node has an "enabled" button, so it can be turned off. Useful if it's slow. Starts true,
                but you could set "enabled" to false on the node in the init() method.
            startEnabled - only applies if hasEnable is true. If False, the node starts disabled. This is
                a good setting for really, REALLY slow nodes.
        """
        self.group = group
        self.name = name
        self.ver = ver
        self.helpwin = None
        self.hasEnable = hasEnable
        self.oldNames = set()  # set of old names, add the old names in the type constructor.
        self.startEnabled = startEnabled
        # this contains tuples of (name, connector type (a datum Type), desc).
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
        self.minwidth = 100
        self.defaultWidth = self.minwidth
        self.defaultHeight = graphscene.NODEHEIGHT
        self.resizable = False
        self.showPerformedCount = True
        self.setRectParams = None
        # nodes with this flag ALWAYS run, but they always run after all other nodes (unless they have children,
        # which run after them). It also never skips due to unset inputs, because these might be because the
        # parent node threw an exception.
        self.alwaysRunAfter = False

        # If this is not None, then this type has a set of parameters which can be
        # edited in a parameter file. These will be serialised using a different
        # mechanism. This field will contain information about those parameters as
        # TaggedAggregateType objects (typically a structure with a TaggedDictType at the root).
        # Within each node, a mirror of that structure containing the actual data will
        # exist, such as a TaggedDict.

        self.params = None

    def md5(self):
        """returns a checksum of the sourcecode for the module defining the type, MD5 hash, used to check versions"""
        return self._md5

    def doAutoserialise(self, node):
        """run autoserialisation for a node"""
        try:
            # if elements are tuples (i.e. value and default), only get the first item
            ser = [f[0] if type(f) == tuple else f for f in self.autoserialise]
            # and build the dictionary
            return {name: node.__dict__[name] for name in ser}
        except KeyError as e:
            raise Exception("autoserialise value not in node {}: {}".format(self.name, e.args[0]))

    def getAutoserialiseDefault(self, name):
        """Really ugly because of the way autoserialise was developed. This gets a default, if there is one!"""
        for t in self.autoserialise:
            if isinstance(t,tuple):
                n, d = t
                if name == n:
                    return d
        raise Exception(f"autoserialise value must have a default for getAutoSerialiseDefault: {name}")

    def doAutodeserialise(self, node, ent):
        """run autodeserialisation for a node"""
        for item in self.autoserialise:
            if type(item) == tuple:
                name, deflt = item
                node.__dict__[name] = ent.get(name, deflt)
            else:
                node.__dict__[item] = ent.get(item)

    def addInputConnector(self, name, conntype, desc=""):
        """create a new input connector; done in subclass constructor"""
        self.inputConnectors.append((name, conntype, desc))

    def addOutputConnector(self, name, conntype, desc=""):
        """create a new output connector; done in subclass constructor"""
        self.outputConnectors.append((name, conntype, desc))

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
        If you're doing "complex TaggedAggregate serialisation" this should also build a params field
        in the node containing a TaggedDict of the appropriate type.
            This happens in addition to autoserialisation/deserialisation
        """
        pass

    def deserialise(self, xform, d):
        """maybe override - given a dictionary, set the values in the node from the dictionary.
        If you are doing "complex TaggedAggregate serialisation" you should probably leave this
        alone and instead write a nodeDataFromParams() method.
            This happens in addition to autoserialisation/deserialisation
        """
        pass

    def nodeDataFromParams(self, xform):
        """override if you are doing "complex TaggedAggregate serialisation - build the node's data
        from the node's .params field."""
        pass

    def createTab(self, xform, window):
        """usually override this - create a tab connected to this xform, parented to a main window.
            Might return none, if this xform doesn't have a meaningful UI.
            """
        return None

    def clearData(self, xform):
        """
        Some nodes generate data that isn't in an output, possibly for display. These nodes can override this method.
        """
        pass

    def getBatchOutputValue(self, node):
        """
        Similarly, some nodes generate output values which can be saved by a runner, but don't necessarily
        have an actual output. We can get that behaviour here. By default, this will return the first output,
        but nodes like "sink" which don't have an output can override it. It will also throw an error if there
        is no first output.
        """
        if len(self.outputConnectors) == 0:
            raise Exception(f"Node type {self.name} has no output connectors")
        else:
            return node.getOutputDatum(0)

    def getDisplayName(self, n):
        """Return the display text. Usually this is the displayName field but it can be overriden (which is why
        it's in the type class, not the node class"""
        return n.displayName

    def buildTextWithFont(self, n, font):
        """Used to build the text for the rectangle in buildText. None for the font means use default"""
        x, y = n.xy
        nam = self.getDisplayName(n)
        text = graphscene.GText(n.rect, nam, n)
        text.setPos(x + graphscene.XTEXTOFFSET, y + graphscene.YTEXTOFFSET + graphscene.CONNECTORHEIGHT)
        text.setFont(font if font else graphscene.mainFont)
        return text

    def buildText(self, n):
        """build the text element of the graph scene object for the node.
        By default, this will just create static text, but can be overridden.
        The text will be in bold if the node has been renamed.
        """
        f = None if n.displayName == self.name else graphscene.boldMainFont
        return self.buildTextWithFont(n, f)

    def resizeDone(self, n):
        """The node's onscreen box has been resized"""
        pass

    def getDefaultRectColour(self, n):
        return 255, 255, 255

    def getTextColour(self, n):
        return 0, 0, 0


def serialiseConn(c, connSet):
    """serialise a connection (xform,i) into (xformName,i).
    Will only serialise connections within the set passed in. If None is passed
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


performDepth = 0

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
    # the "overriding" output type (a node may change its type when it performs)
    outputTypes: List[Optional[str]]

    ## @var inputTypes
    # the "overriding" input types (used in macros)
    inputTypes: List[Optional[str]]

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

    # the screen coordinates
    xy: Tuple[int, int]
    # screen width
    w: Optional[int]
    # screen height
    h: Optional[int]

    # a list of open tabs
    tabs: List['pcot.ui.tabs.Tab']
    # is this the currently selected node?
    current: bool
    # the main rectangle for the node in the scene
    rect: ['graphscene.GMainRect']
    # input connector rectangles
    inrects: List[Optional['graphscene.GConnectRect']]
    # output connector rectangles
    outrects: List[Optional['graphscene.GConnectRect']]
    # error state or None. See XFormException for codes.
    error: Optional[XFormException]
    # extra text displayed (if there's no error)
    rectText: Optional[str]
    # the time this node took to run in the last call to performNodes
    runTime: float
    # recursion avoidance
    inUIChange: bool

    # the serialised parameters in a TaggedAggregate, or None. Usually it's TaggedDict.
    params: Optional['TaggedAggregate']

    def __init__(self, tp, dispname):
        """constructor, takes type and displayname"""
        self.instance = None
        self.type = tp
        self.savedver = tp.ver
        self.savedmd5 = None
        # we keep a dict of those nodes which get inputs from us, and how many. We can't
        # keep the actual output connections easily, because they are one->many.
        self.children = {}
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
        self.timesPerformed = 0  # used for debugging/optimising
        self.rebuildTabsAfterPerform = False

        # create default parameter data
        self.params = None if tp.params is None else tp.params.create()

        # UI-DEPENDENT DATA DOWN HERE

        # this SHOULD be serialised
        self.xy = (0, 0)
        self.w = self.type.defaultWidth
        self.h = self.type.defaultHeight

        # this stuff shouldn't be serialized
        # on-screen geometry, which should be set before we try to draw it
        self.tabs = []  # no tabs open
        self.current = False
        self.rect = None  # the main GMainRect rectangle
        self.enabled = tp.startEnabled  # a lot of nodes won't use; see XFormType.
        self.hasRun = False  # used to mark a node as already having performed its stuff
        self.inUIChange = False
        # all nodes have a channel mapping, because it's easier. See docs for that class.
        self.mapping = ChannelMapping()
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

    def getDisplayName(self):
        """Return the display text. Usually this is the displayName field but it can be overriden, e.g.
        by expr where the expression is displayed if the name is "expr" """
        return self.type.getDisplayName(self)

    def clearOutputsAndTempData(self):
        """
        clear all the node's outputs, required on all nodes before we run the graph
        (it's how we check a node can run - are all its input nodes' outputs set?). Also
        clear other data which is generated by running the node.
        """
        self.outputs = [None for _ in self.type.outputConnectors]
        self.type.clearData(self)

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
        # these are None. We also clear other data generated by running.
        self.clearOutputsAndTempData()
        # these are the overriding output types; none if we use the default
        # given by the type object (see the comment on outputConnectors
        # in XFormType)
        self.outputTypes = [None for _ in self.type.outputConnectors]
        self.inputTypes = [None for _ in self.type.inputConnectors]
        self.inrects = [None for _ in self.inputs]  # input connector GConnectRects
        self.outrects = [None for _ in self.outputs]  # output connector GConnectRects

    def onRemove(self):
        """called when a node is deleted"""
        self.graph.doc.nodeRemoved(self)

    def setEnabled(self, b):
        """set or clear the enabled field"""
        self.enabled = b
        for x in self.tabs:
            x.setNodeEnabled()
        self.graph.scene.selChanged()
        self.graph.changed(self)

    def serialise(self):
        """build a serialisable python dict of this node's values - including any connections from nodes
        not in the set. """
        d = {'xy': self.xy,
             'w': self.w,
             'h': self.h,
             'type': self.type.name,
             'displayName': self.displayName,
             'ins': [serialiseConn(c, None) for c in self.inputs],
             'outputTypes': [None if x is None else x.name for x in self.outputTypes],
             'inputTypes': [None if x is None else x.name for x in self.inputTypes],
             'md5': self.type.md5(),
             'ver': self.type.ver,
             'mapping': self.mapping.serialise()}
        if self.type.hasEnable:  # only save 'enabled' if the node uses it
            d['enabled'] = self.enabled

        # add autoserialised data
        d.update(self.type.doAutoserialise(self))
        # and run the additional serialisation tasks, serialising things which
        # can't be autoserialised (because they aren't JSON-serialisable) and
        # perhaps converting data into self.params fields.
        d2 = self.type.serialise(self)
        if d2 is not None:
            # avoids a type check problem
            d.update(d2 or {})

        Canvas.serialise(self, d)

        # serialise the parameters into the same dict
        if self.params is not None:
            # but flag an error if there are keys which already exist because that will cause problems
            # when deserialising.
            d2 = self.params.serialise()
            intersect = set(d.keys()).intersection(set(d2.keys()))
            if len(intersect) > 0:
                raise Exception(f"Parameter keys already exist in serialised node data: {intersect} (are you using both TaggedAggregate and autoserialise?)")
            d.update(d2)
        return d

    def deserialise(self, d):
        """deserialise a node from a python dict.
        Some entries have already been already dealt with."""
        self.xy = d['xy']
        self.w = d.get('w', self.type.defaultWidth)  # use 'get' to still be able to load early data
        self.h = d.get('h', self.type.defaultHeight)
        # these are the overriding types - if the value is None, use the xformtype's value, else use the one here.
        self.outputTypes = [None if x is None else datum.deserialise(x) for x in d['outputTypes']]
        self.inputTypes = [None if x is None else datum.deserialise(x) for x in d['inputTypes']]
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
        # deserialise parameter data which need to be processed another way, not via
        # self.type.params and self.params
        # deserialise parameters
        if self.type.params is not None:
            # this will replace the defaults.
            try:
                self.params = self.type.params.deserialise(d)
            except ValueError as e:
                logger.critical(f"Error deserialising parameters for node {self.displayName}: {str(e)}")
                ui.log(f'  <font color="red"><b>Error deserialising parameters for node {self.displayName}</b></font>')
                ui.log(f'  <font color="red"><b>{str(e)}</b></font>')
        # finally do any extra deserialisation tasks, such as deserialising things which
        # can't be autoserialised and such as converting self.params into data
        self.type.deserialise(self, d)
        self.type.nodeDataFromParams(self)

    def getOutputType(self, i) -> Optional['pcot.datumtypes.Type']:
        """return the actual type of an output, taking account of overrides (node outputTypes).
        Note that this returns the *connection* type, not the *datum* type stored in that connection.
        Returns None if there is no connection, not Datum.NONE.
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

    def getOutputDatum(self, i):
        """Get a 'raw' output as just a datum"""
        try:
            return self.outputs[i]  # may raise IndexError
        except IndexError as e:
            raise IndexError(f"Node '{self.displayName}' has no output {i}") from e

    def getOutput(self, i, tp=None):
        """get an output, raising an exception if the type is incorrect or the index is output range
        used in external code; compare with Datum.get() which doesn't raise. Dereferences the output,
        so you get the value stored in the Datum.
        """
        d = self.outputs[i]  # may raise IndexError
        if d is None:
            return None
        elif tp is None or d.tp == tp or tp == Datum.IMG and d.isImage():
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
        #        old = self.outputTypes[index]
        self.outputTypes[index] = tp
        if self.outrects[index] is not None:
            #            print("MATCHING: {} becomes {}".format(index,type))
            self.outrects[index].typeChanged()

    #        if old != tp:
    #            self.graph.rebuildGraphics()

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
        alw = "-ALWAYS" if self.type.alwaysRunAfter else ""
        return f"{self.type.name}/{self.name}/{self.displayName}{alw}"

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
            But it does check connection numbers.
            """
        if self is other:
            raise XFormException('DATA', 'cannot connect output to input of same node!')
        if inputIdx < 0:
            raise XFormException('DATA', 'cannot connect to negative input')
        if output < 0:
            raise XFormException('DATA', 'cannot connect to negative output')
        if inputIdx >= len(self.inputs):
            ui.error(f"Input index out of range when connecting {other.debugName()}:{output} to {self.debugName()}:{inputIdx}", False)
            return
            # raise XFormException('DATA', 'input index out of range')
        if output >= len(other.type.outputConnectors):
            ui.error(f"Output  index out of range when connecting {other.debugName()}:{output} to {self.debugName()}:{inputIdx}", False)
            return
            # raise XFormException('DATA', 'output index out of range')

        if not self.cycle(other):  # this is a double check, the UI checks too.
            self.inputs[inputIdx] = (other, output)
            other.increaseChildCount(self)
            if autoPerform:
                other.graph.changed(other)  # perform the input node; the output should perform

    def disconnect(self, inputIdx, perform=True):
        """disconnect an input"""
        if 0 <= inputIdx < len(self.inputs):
            if self.inputs[inputIdx] is not None:
                n, i = self.inputs[inputIdx]
                n.decreaseChildCount(self)
                self.inputs[inputIdx] = None
                if perform:
                    self.graph.changed(self)  # run perform safely

    def disconnectAll(self):
        """disconnect all inputs and outputs prior to removal"""
        for i in range(0, len(self.inputs)):
            self.disconnect(i, perform=False)
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
        if data is not None and not isinstance(data, Datum):
            raise Exception("setOutput requires a Datum or None, not a raw value")
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
        if self.type.alwaysRunAfter:
            return True
        for inp in self.inputs:
            # unconnected inputs are OK (otherwise e.g. spectrum could never run) but connected inputs with
            # no data on them, less so.
            if inp is not None:
                out, index = inp
                if out.outputs[index] is None:
                    return False
        return True

    def updateTabs(self):
        """Tell the node to update its tabs; calls nodeChanged and updateError for each tab. The former
        will tell the tab to update itself from the node, the latter will update the error field."""
        for x in self.tabs:
            x.nodeChanged()
            x.updateError()

    ## perform the transformation; delegated to the type object - recurses down the children.
    # Also tells any tab open on a node that its node has changed.
    # DO NOT CALL DIRECTLY - called either from itself or from performNodes.
    def perform(self, isAlwaysRunAfter=False):
        global performDepth

        # don't run "always run after" special nodes unless we're allowed.
        if self.type.alwaysRunAfter and not isAlwaysRunAfter:
            return

        # used to stop perform being called out of context; it should
        # only be called inside the graph's perform.
        if not self.graph.performingGraph:
            raise Exception("Do not call perform directly on a node!")
        ui.msg("Performing {}".format(self.debugName()))
        self.timesPerformed += 1
        try:
            # must clear this with prePerform on the graph, or nodes will
            # only run once!
            if self.hasRun:
                logger.debug(f"----Skipping {self.debugName()}, run already this action")
            elif not self.canRun():
                logger.debug(f"----Skipping {self.debugName()}, it can't run (unset inputs)")
            else:
                logger.debug(f"---------------------------------{'-'*performDepth}Performing {self.debugName()}")
                # now run the node, catching any XFormException
                try:
                    st = time.perf_counter()
                    self.type.uichange(self)
                    # here we check that the node is enabled. If it is NOT, we set all the outputs to None.
                    # Thus a disabled node will behave exactly as if it has an unconnected input
                    # (as in test_node_output_none)
                    # We also check the forceRunDisabled flag in the graph - this is set when we want to
                    # force all nodes - disabled or not - to run. Typically this is done from a script.
                    if self.enabled or self.graph.forceRunDisabled:
                        self.type.perform(self)
                    else:
                        # this may end up being done twice, because we do it to all nodes before we run the graph
                        self.clearOutputsAndTempData()
                    self.runTime = time.perf_counter() - st
                except XFormException as e:
                    # exception caught, set the error. Children will still run.
                    self.setError(e)
                self.hasRun = True
                # tell the tab that this node has changed
                self.updateTabs()

                # this is a hack to let us guarantee the order children are processed,
                # by sorting them by display name. Used in testing.
                sorted_children = sorted(self.children.keys(), key=lambda xx: xx.displayName)

                # run each child (could turn off child processing?)
                performDepth += 1
                for n in sorted_children:
                    n.perform()
                performDepth -= 1
        except Exception as e:
            traceback.print_exc()
            ui.logXFormException(self, e)

    def getInput(self, i: int, tp=None):
        """get the value of an input.
            Optional type; if passed in will check for that type and dereference the contents if
            matched, else returning null.
            """
        if self.inputs[i] is None:
            # if we're asking for a particular type, "dereference" the
            # None and return None directly. Otherwise, wrap the None in
            # a Datum, but we don't know what type to use so just say ANY.
            return Datum(Datum.ANY, None, nullSourceSet) if tp is None else None
        else:
            n, i = self.inputs[i]
            o = n.outputs[i]

            if tp is None:
                # no type checking done, we return the Datum
                if o is None:
                    # ... except there isn't one, so invent one.
                    return Datum(Datum.ANY, None, nullSourceSet)
                else:
                    # all is well, return the Datum.
                    return o
            elif o is None:
                # we have a null input
                return None
            elif not datum.isCompatibleConnection(o.tp, tp):
                # we have passed in a type, but it doesn't match. Rather than raise an exception,
                # we create an exception and set the XForm's error state to it, and return None. Effectively
                # we create an exception and deal with it locally.
                self.setError(XFormException('TYPE', f"expected a {tp}, got {o.tp}"))
                return None
            else:
                # we have passed in a type and it matches, so dereference
                return o.val

    def ensureConnectionsValid(self):
        """ensure connections are valid and break them if not"""
        # THIS IS NOW OBSOLETE AND SHOULDN'T BE CALLED
        raise XFormException('TYPE', 'ensureConnectionsValid should not be called (see issue #60)')
        doPerform = False
        for i in range(0, len(self.inputs)):
            inp = self.inputs[i]
            if inp is not None:
                n, idx = inp
                outtype = n.getOutputType(idx)
                intype = self.getInputType(i)
                if not datum.isCompatibleConnection(outtype, intype):
                    doPerform = True
                    self.disconnect(i, perform=False)
        return doPerform

    def rename(self, name):
        """rename a node - changes the displayname."""
        # defer to type, because connector nodes have to rebuild all views.
        self.type.rename(self, name)

    def mark(self):
        """Record the state of the node in the undo mechanism"""
        self.graph.doc.mark()

    def unmark(self):
        self.graph.doc.unmark()

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return "XForm-{}-{}-{}".format(id(self), self.displayName, self.type.name)


class XFormGraph:
    """a graph of transformation nodes: this is the primary PCOT document type"""
    # all my nodes
    nodes: List[XForm]

    # my graphical representation
    scene: Optional['graphscene.XFormGraphScene']

    # true if this is a macro prototype, will be false for instances
    isMacro: bool

    # true when I'm recursively performing my nodes. Avoids parallel
    # attempts to run a graph in different threads.
    performingGraph: bool

    # dictionary of UUID to node, used to get instance nodes from prototypes
    nodeDict: Dict[str, XForm]

    # If this is a macro, the type object for the macro prototype (a singleton of
    # XFormMacro, itself a subclass of XFormType)
    proto: Optional['XFormMacro']

    # texts may have change in perform, need to rebuild tabs
    rebuildTabsAfterPerform: bool

    # the document of which I am a part, whether as the top-level graph or a macro.
    doc: 'Document'

    # should graphs be autorun
    autoRun: ClassVar[bool]
    autoRun = True

    # force all nodes to run, even if they are disabled
    forceRunDisabled: bool

    def __init__(self, doc, isMacro):
        """constructor, takes whether the graph is a macro prototype or not"""
        self.proto = None
        self.doc = doc
        self.nodes = []
        self.performingGraph = False
        self.scene = None  # the graph's scene is created by autoLayout
        self.isMacro = isMacro
        self.nodeDict = {}
        self.rebuildTabsAfterPerform = False
        self.forceRunDisabled = False

    def constructScene(self, doAutoLayout):
        """construct a graphical representation for this graph"""
        self.scene = graphscene.XFormGraphScene(self, doAutoLayout)

    def create(self, typename, displayName=None):
        """create a new node, passing in a type name. We look in both the 'global' dictionary,
        allTypes,  but also the macros for this document. We can pass in an optional display name.
        Will also set a new position."""

        # note that we don't mark here - this is called in deserialisation so that would be bad. We do the mark
        # before the UI calls this.

        if typename in allTypes:
            tp = allTypes[typename]
        elif typename in self.doc.macros:
            tp = self.doc.macros[typename]
        else:
            # ugly search for name in all types' old names
            for t in allTypes.values():
                if typename in t.oldNames:
                    tp = t
                    break
            else:
                # this runs if we didn't break, i.e. we didn't find it
                if "dummy" not in allTypes:
                    raise Exception("Can't find the 'dummy' XFormType - looks like no types have been registered.")
                ui.warn("Transformation type not found: " + typename)
                return self.create("dummy")

        # first, try to make sure we aren't creating a macro inside itself
        if tp.cycleCheck(self):
            raise XFormException('TYPE', "Cannot create a macro which contains itself")

        # first we need to get a position if we have a scene, otherwise 0,0.
        # We need to do this before the node is added to the graph because
        # getNewPosition iterates the graph.
        xy = (0, 0) if self.scene is None else self.scene.getNewPosition()
        # display name is just the type name to start with.
        xform = XForm(tp, tp.name)
        xform.xy = xy   # now we can set the position
        self.nodes.append(xform)
        self.doc.nodeAdded(xform)
        xform.graph = self
        tp.init(xform)  # run the init
        self.nodeDict[xform.name] = xform
        if displayName is not None:
            xform.displayName = displayName
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
        try:
            pyperclip.copy(s)
        except pyperclip.PyperclipException as e:
            ui.error(str(e))
            ui.pyperclipErrorDialog()

    def paste(self):
        """paste the clipboard.
        This involves deserialising.
        Returns a list of new nodes.
        """
        # get data from clipboard as a b64 encoded string
        try:
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
        except pyperclip.PyperclipException as e:
            ui.error(str(e))
            ui.pyperclipErrorDialog()
        return []

    def remove(self, node, closetabs=True):
        """remove a node from the graph, and close any tab/window (but not always; when doing Undo
        we monkey patch the existing tabs to point at the replacement nodes)"""

        if node in self.nodes:
            oldChildren = list(node.children)  # shallow copy of children
            node.disconnectAll()  # because it gets cleared here
            if closetabs:
                for x in node.tabs:
                    x.nodeDeleted()
            self.nodes.remove(node)
            logger.debug(f"DELETE {node.name} {node.type.name}")
            del self.nodeDict[node.name]

            # having deleted the node try to call all the children. That might seem a bit
            # weird, but should clear any errors resulting from (say) a bad type being
            # issued by the deleted node.

            for x in oldChildren:
                self.performNodes(x)
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
        self.rebuildTabsAfterPerform = False
        nodeset = set()
        if root is not None:
            self.visit(root, lambda x: nodeset.add(x))
        else:
            nodeset = set(self.nodes)
        for n in nodeset:
            n.clearErrorAndRectText()
            n.clearOutputsAndTempData()
            n.hasRun = False
        for n in self.nodes:
            n.runTime = None

    def changed(self, node=None, runAll=False, uiOnly=False, forceRunDisabled=False, invalidateInputs=True):
        """Called when a control in a node has changed, and the node needs to rerun (as do all its+ children recursively).
        If called on a normal graph, will perform the graph or a single node within it,
        and all dependent nodes; called on a macro will do the same thing in instances, starting at the
        counterpart node for that in the macro prototype.

        If forceRunDisabled is true, any disabled nodes will be temporarily activated.
        This allows scripts with disabled nodes to run correctly.

        We don't want to invalidate inputs and force a reload when doing undo/redo. This is because
        the data may have gone away (issue #58). So we have a flag to avoid this.
        """

        self.forceRunDisabled = forceRunDisabled
        if (not uiOnly) and (XFormGraph.autoRun or runAll):
            if runAll and invalidateInputs:
                self.doc.inputMgr.invalidate()
            if self.isMacro:
                # distribute changes in macro prototype to instances.
                # what we do here is go through all instances of the macro. 
                # We copy the changed prototype to the instances, then run
                # the instances in the graphs which contain them (usually the
                # main graph).
                # This could be optimised to run only the relevant (changed) component
                # within the macro, but that's very hairy.

                for inst in self.proto.getInstances():
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
            # to every node before perform() when autorun is on (hence the elif below). We need recursion avoidance
            # here too, like happens in perform.

            node.type.uichange(node)

            # and update tabs.
            node.updateTabs()
            ui.msg("Autorun not enabled")

        # make sure the caption in any attached window is correct.
        for xx in ui.mainwindow.MainUI.windows:
            if xx.graph == self:
                xx.setCaption(self.doc.settings.captionType)

        self.forceRunDisabled = False

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
                # identify root nodes (no connected inputs) which are NOT alwaysRun.
                if all(i is None for i in n.inputs) and not n.type.alwaysRunAfter:
                    n.perform()
            # having run the root nodes, run those nodes which have the 'alwaysRunAfter' flag
            # in their type. These are used in testing.
            for n in self.nodes:
                if n.type.alwaysRunAfter:
                    n.perform(isAlwaysRunAfter=True)
        else:
            # we're running an explicit node
            node.perform()
        self.performingGraph = False

        self.showPerformance()

        # force a rebuild of the scene; error states may have changed.
        self.rebuildGraphics()
        if self.rebuildTabsAfterPerform:
            self.rebuildTabsAfterPerform = False
            ui.mainwindow.MainUI.rebuildAll(scene=False)
        ui.msg("Perform complete")

    def showPerformance(self):
        """show how long each node took to run"""
        tot = 0
        for n in sorted([x for x in self.nodes if x.runTime is not None], key=lambda x: x.runTime):
            tot = tot + n.runTime
            logger.debug("{:<10.3f} {} ".format(n.runTime, n.displayName))
        logger.debug("{:<10.3f} TOTAL".format(tot))

    def rebuildGraphics(self):
        """rebuild all graphics elements if a scene is present"""
        if self.scene is not None:
            self.scene.rebuild()

    ## a node's input has changed, which may change the output types.
    def inputChanged(self, node):
        # rebuild the types, perhaps replacing None (use the type default) with
        # a type name
        node.type.generateOutputTypes(node)

    def serialise(self, items=None):
        """serialise all nodes into a dict"""
        # just serialise all the nodes into a dict, or those in a list.
        d = {}
        if items is None:
            items = self.nodes
        for n in items:
            d[n.name] = n.serialise()

        return d

    def clearAllNodes(self, closetabs=True):
        """Delete all nodes - done on deserialising into an existing graph and on clearing a document"""
        # we temporarily disable graph performance by telling the system we are already
        # performing a graph. This will stop it doing it again, which messing things up
        # because we perform child nodes on .remove. Well, it doesn't mess things up
        # fatally but you do get a lot of spurious errors.
        oldPerfG = self.performingGraph
        self.performingGraph = True
        # remove from a copy; can't modify a list while traversing
        for n in self.nodes.copy():
            # this will close any open tabs, but NOT when closetabs is false.
            self.remove(n, closetabs=closetabs)
        self.performingGraph = oldPerfG

    def deserialise(self, d, deleteExistingNodes, closetabs=True):
        """given a dictionary, add nodes stored in it in serialized form.
            Do not delete any existing nodes unless asked and do not perform the nodes.
            Returns a list of the new nodes.
            Will leave tabs open pointing to the dead nodes when closetabs is false - the
            app must then patch these tabs to point to replacement nodes, if they exist.
            If not they should be closed. This is used in undo/redo.
            """

        if deleteExistingNodes:
            self.clearAllNodes(closetabs=closetabs)

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
                    if oname in self.nodeDict:
                        # only do the connection if the node we're connecting from is found
                        other = self.nodeDict[oname]
                        n.connect(i, other, output, False)  # don't automatically perform
        # and finally match output types
        for n in newnodes:
            n.type.generateOutputTypes(n)
        return newnodes

    def get(self, name):
        """Really ugly thing for getting a node by name. Node names are unique.
        The *correct* thing to do would be have a dict of
        nodes by name, of course. But this is plenty fast enough.
        These nodes are not visible to the user. SEE ALSO: getByDisplayName()"""
        for n in self.nodes:
            if n.name == name:
                return n
        return None

    def nodeExists(self, name):
        """Does a node exist (node names are unique)?"""
        return self.get(name) is not None

    def getByDisplayName(self, name, single=False):
        """Return a list of nodes which have this display name. if single is True, return
        the first one only and ensure there is only one item."""
        name = name.strip()
        x = [x for x in self.nodes if x.getDisplayName() == name]
        if single:
            if len(x) == 1:
                return x[0]
            else:
                raise ValueError("Expected one node with display name {}, found {}".format(name, len(x)))
        else:
            return x

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
            and break those which aren't. Reperform the graph if there was a change.
            """
        doPerform = False
        for n in self.nodes:
            doPerform |= n.ensureConnectionsValid()
        if doPerform:
            self.changed()

    def getMyROIs(self, node):
        """If this node creates an ROI or ROIs, return it/them as a list, otherwise None (not an empty list)"""
        return None

    def nodeDataFromParams(self):
        """Used in the parameter file runner to set the node data from parameters which have been
        modified since the node was created. This does mean this gets called at least twice - once
        when the node is created, and once when the node is modified."""
        for n in self.nodes:
            n.type.nodeDataFromParams(n)

    def getAnyErrors(self) -> List[XForm]:
        """Return a list of all nodes which have errors in the graph - used in batch files after a run"""
        return [x for x in self.nodes if x.error is not None]


class XFormROIType(XFormType):
    """Class for handling ROI xform types, does most of the heavy lifting of the node's perform
    function. The actual ROIs are dealt with in imagecube.py"""

    # constants enumerating connections
    IN_IMG = 0

    OUT_IMG = 0
    OUT_ROI = 1

    def __init__(self, name, group, ver):
        super().__init__(name, group, ver)
        self.addInputConnector("input", Datum.IMG)
        self.addOutputConnector("img", Datum.IMG, "image with ROI")  # image+roi
        self.addOutputConnector("roi", Datum.ROI, "the region of interest")

    def setProps(self, node, img):
        """Set properties in the node and ROI attached to the node. Assumes img is a valid
        imagecube, and node.roi is the ROI"""
        pass

    def perform(self, node):
        img = node.getInput(self.IN_IMG, Datum.IMG)
        # label the ROI
        node.setRectText(node.roi.label)

        if img is None:
            # no image
            outImgDatum = Datum(Datum.IMG, None, nullSourceSet)
            outROIDatum = Datum(Datum.ROI, None, nullSourceSet)
        else:
            # new image's sources are a combo of the image sources and that of the ROI
            # So first we build a list of copies of the ROI source set, 1 for each channel. We turn that into
            # a multibandsource.
            tmp = MultiBandSource([node.roi.sources for _ in img.sources.sourceSets])
            # then we create a bandwise union between this and the image's source sets.
            sources = MultiBandSource.createBandwiseUnion([tmp, img.sources])
            self.setProps(node, img)
            # copy image and append ROI to it
            img = img.copy()
            node.roi.setContainingImageDimensions(img.w, img.h)
            img.rois.append(node.roi)
            # set mapping from node
            img.setMapping(node.mapping)

            outImgDatum = Datum(Datum.IMG, img, sources)
            outROIDatum = Datum(Datum.ROI, node.roi, node.roi.sources)  # not a copy!

        node.setOutput(self.OUT_IMG, outImgDatum)
        node.setOutput(self.OUT_ROI, outROIDatum)

    def uichange(self, node):
        """Fix for Issue #42: changing colour mapping on ROI nodes not working.
        This is called when the UI changes - typically when we edit the canvas' mapping.
        Because the canvas mapping determines the OUT_ANNOT output, we need to run children.
        This gets called from inside the canvas itself, in redisplay(), because display()
        has set the nodeToUIChange field."""

        # yet more recursion avoidance, this time the simple uichange->changed->uichange... cycle
        # that can happen when autorun is off
        if not node.inUIChange:
            node.inUIChange = True
            node.graph.changed(node)
            node.inUIChange = False

    def getROIDesc(self, node):
        return "no ROI" if node.roi is None else node.roi.details()
