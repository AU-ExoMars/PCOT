"""Code dealing with macros and macro prototypes"""
import logging
from typing import List

import pcot.ui.mainwindow
import pcot.xform as xform
from pcot import datum
from pcot.datum import Datum
from pcot.imagecube import ChannelMapping
from pcot.ui.tabs import Tab
from pcot.utils import deb
from pcot.xform import XFormType, XFormGraph

logger = logging.getLogger(__name__)


class MacroInstance:
    """This is the instance of a macro, containing its copy of the graph
    and some metadata. Refactoring note - this class used to be a lot bigger
    and things gradually got moved into the node itself. That's now probably
    the best place for them, although copyProto is a problem.
    """
    ## @var proto
    # The XFormMacro object which is the macro prototype
    ## @var node
    # The XForm node which holds this macro instance
    ## @var graph
    # The XFormGraph which is this instance of the macro - not to be confused
    # with the macro's prototype graph, which is stored in proto.graph.

    def __init__(self, proto, node):
        """construct, taking the XFormMacro prototype object and the XForm I am inside."""
        self.proto = proto
        self.node = node  # backpointer to the XForm containing me
        self.graph = xform.XFormGraph(proto.doc, False)  # create an empty graph, not a macro prototype

    def copyProto(self):
        """this serialises and then deserialises the prototype's
        graph, giving us a fresh copy of the nodes. However, the UUID "names"
        are the same so that corresponding nodes in instance and copy
        have the same UUID (not really "U", but you get the idea)"""
        d = self.proto.graph.serialise()
        self.proto.graph.dump()
        logger.debug(f"PROTOTYPE keys: {self.proto.graph.nodeDict.keys()}")
        self.graph.deserialise(d, True)


class XFormMacroConnector(XFormType):
    """these are the connections for macros, which should only be added to macros.
    For that reason they are not decorated with @xformtype. However, they do
    get added to allTypes.

    Additional fields in the XForms:
    - proto points to the containing XFormMacro
    - idx indexes the connector
    - conntype is the type of the connection (a string)
    - data is the data stored

    """
    def __init__(self, name):
        super().__init__(name, "hidden", "0.0.0")
        self.displayName = '??'  # forces a rename in setConnectors first time
        self._md5 = ''  # we ignore the MD5 checksum for versioning
        self.autoserialise = ('idx',)

    def init(self, node):
        node.datum = None
        node.conntype = Datum.VARIANT

    def serialise(self, node):
        """called from XForm.serialise, saves the macro name"""
        return {'macro': node.proto.name,
                'conntype': node.conntype.name}

    def deserialise(self, node, d):
        """called from XFormMacro.deserialise, finds the macro"""
        name = d['macro']
        doc = node.graph.doc
        if name not in doc.macros:
            raise Exception('macro {} not found'.format(name))
        node.proto = doc.macros[name]
        node.conntype = datum.deserialise(d['conntype'])
        node.proto.setConnectors()

    def remove(self, node):
        """when connectors are removed, the prototype's connectors must change (and
        thus those of all the instances)"""
        node.proto.setConnectors()

    def rename(self, node, name):
        """force renaming of connectors on instance nodes and in the prototype"""
        super().rename(node, name)
        node.proto.setConnectors()  # forces rename of connectors on instance nodes

    def createTab(self, node, window):
        """create the edit tab"""
        return TabConnector(node, window)


@xform.xformtype
class XFormMacroIn(XFormMacroConnector):
    """The macro input connector (used inside macro prototypes)"""
    def __init__(self):
        super().__init__("in")
        # does not appear until specified by the user
        self.addOutputConnector("", Datum.VARIANT)

    def perform(self, node):
        """perform sets the output from data set in XFormMacro.perform()"""
        if node.getOutputType(0) == Datum.VARIANT:
            raise xform.XFormException('TYPE', 'output type of macro input node must be specified')
        node.setOutput(0, node.datum)
        logger.debug(f"DUMP OF INCONNECTOR {node.name}, {node}")
        if logger.isEnabledFor(logging.DEBUG):
            node.dump()
        logger.debug(f"CONNECTOR OUTPUT {node.datum}")


@xform.xformtype
class XFormMacroOut(XFormMacroConnector):
    """The macro output connector (used inside macro prototypes)"""
    def __init__(self):
        super().__init__("out")
        # does not appear until specified by the user
        self.addInputConnector("", Datum.VARIANT)

    def perform(self, node):
        """perform stores its input in its data field, ready for XFormMacro.perform() to read it"""
        if node.getInputType(0) == Datum.VARIANT:
            raise xform.XFormException('TYPE', 'input type of macro output node must be specified')
        node.datum = node.getInput(0)
        logger.debug(f"DUMP OF OUTCONNECTOR {node.name}, {node}")
        if logger.isEnabledFor(logging.DEBUG):
            node.dump()
        logger.debug(f"CONNECTOR OUTPUT {node.datum}")


class XFormMacro(XFormType):
    """the actual macro xform type - this doesn't get autoregistered because a new one is created'
    for each individual macro prototype. A macro consists of a graph and links to any macro instances,
    so that changes in the prototype can be reflected in the instances. It also contains its own
    XFormType object, based on XFormMacro but with a unique name and different connectors."""

    ## @var graph
    # the graph for this prototype
    graph: xform.XFormGraph

    ## @var inputNodeNames
    # the UUIDs for input nodes in the prototype
    inputNodes: List[str]

    ## @var outputNodeNames
    # the UUIDs for output nodes in the prototype
    outputNodes: List[str]

    ## Document
    doc: 'Document'

    def __init__(self, doc, name):
        """initialise, creating a new unique name if none provided."""
        # generate name if none provided
        if name is None:
            name = doc.getUniqueUntitledMacroName()
        # superinit
        super().__init__(name, "macros", "0.0.0")
        self._md5 = ''  # we ignore the MD5 checksum for versioning
        self.doc = doc
        # create our prototype graph 
        self.graph = xform.XFormGraph(doc, True)
        # backpointer to this type object
        self.graph.proto = self
        # ensure unique name
        if name in doc.macros:
            raise Exception("macro {} already exists".format(name))
        # register with the class dictionary
        doc.macros[name] = self
        # initialise the (empty) connectors and will also add us to
        # the palette
        self.setConnectors()

    def getInstances(self):
        return self.doc.getInstances(self)

    def init(self, node):
        """This creates an instance of the macro by setting the node's instance value to a
        new MacroInstance. Other aspects of the xform's macro behaviour are, of course,
        controlled by setting the node's type, which is done elsewhere."""

        # create the macro instance (a lot of which could probably be folded into here,
        # but it's like this for historical reasons actually going waaaay back to
        # the 90s).
        # Remember that this is called to create an instance of the XForm type, which in
        # this case is an instance of the macro.
        node.instance = MacroInstance(self, node)
        node.instance.copyProto()  # copy the graph from the prototype
        node.mapping = ChannelMapping()  # RGB channel mapping for image
        node.sinkimg = None

    def setConnectors(self):
        """Counts the input/output connectors inside the macro and sets the XFormType's
        inputs and outputs accordingly, finally changing connector counts and types on
        the instances."""

        # count input and output connectors. Potential issue: the graphic labelling of
        # the connectors has to match the indices!
        inputs = 0
        outputs = 0
        self.inputConnectors = []
        self.outputConnectors = []
        self.inputNodes = []
        self.outputNodes = []

        # We modify the display name and index of each IO node.
        # We also add it to this type's connectors.
        # The nodes list must be in create order, so that when we do connCountChanged on
        # the instance objects any new nodes get put at the end.
        for n in self.graph.nodes:
            if n.type.name == 'in':
                # only rename if name is still "??" (set in ctor)
                if n.displayName == '??':
                    n.displayName = "in " + str(inputs)
                n.idx = inputs
                # set the connector on the macro object
                self.inputConnectors.append((n.displayName, n.conntype, 'macro input'))
                self.inputNodes.append(n.name)
                # set the connector on the node itself
                n.outputTypes[0] = n.conntype
                inputs += 1
            elif n.type.name == 'out':
                if n.displayName == '??':
                    n.displayName = "out " + str(outputs)
                n.idx = outputs
                self.outputConnectors.append((n.displayName, n.conntype, 'macro output'))
                self.outputNodes.append(n.name)
                n.inputTypes[0] = n.conntype  # set the overrides
                outputs += 1
        # rebuild the various connector structures in each instance
        for n in self.getInstances():
            n.connCountChanged()

        # and we're also going to have to rebuild the palette, so inform all main
        # windows
        pcot.ui.mainwindow.MainUI.rebuildPalettes()
        # and rebuild absolutely everything IF the graph has a scene.
        pcot.ui.mainwindow.MainUI.rebuildAll()

    def renameType(self, newname):
        """renaming a macro - we have to update more things than default XFormType rename"""
        import pcot.ui
        # rename all instances if their displayName is the same as the old type name
        for x in self.getInstances():
            if x.displayName == self.name:
                x.displayName = newname
        # do the default
        # then rename in the macro dictionary
        del self.doc.macros[self.name]
        self.doc.macros[newname] = self
        pcot.ui.mainwindow.MainUI.rebuildPalettes()
        pcot.ui.mainwindow.MainUI.rebuildAll()

    def cycleCheck(self, g: XFormGraph):
        """we are about to insert this macro into the prototype graph g. Return true if this would make a cycle."""
        if self.graph == g:
            return True
        # for every node in here, make sure it's not a macro whose prototype graph is g
        for x in self.graph.nodes:
            if x.type.cycleCheck(g):
                return True
        return False

    def serialise(self, node):
        """serialise an individual macro instance node by storing the macro name"""
        if node.instance is not None:
            name = node.instance.proto.name
        else:
            name = None
        return {'proto': name}

    def deserialise(self, node, d):
        """deserialise an individual macro instance node by dereferencing the macro
        name and creating a new MacroInstance"""

        name = d['proto']
        doc = node.graph.doc
        if name is None:
            node.instance = None
        else:
            if name in doc.macros:
                MacroInstance(doc.macros[name], node)
            else:
                pcot.ui.error("Cannot find macro {} in internal dict".format(name))

    @staticmethod
    def deleteMacro(xformtype):
        """delete a macro"""
        # delete all instances
        toRebuild = set()
        for x in xformtype.doc.nodeInstances[xformtype]:
            x.graph.remove(x)
            toRebuild.add(x.graph)
        for x in toRebuild:
            x.rebuildGraphics()
        # and now the macro itself from the doc
        del xformtype.doc.macros[xformtype.name]
        # caller rebuilds palettes

    def createTab(self, n, w):
        """creates edit tab"""
        return TabMacro(n, w)

    def perform(self, node):
        """perform the macro!"""
        # get the instance graph's node dictionary
        nodedict = node.instance.graph.nodeDict

        # copy the inputs from the node's inputs into the input connector nodes 
        for i in range(0, len(node.inputs)):
            # get the input data
            data = node.getInput(i)
            # get the connector node name
            connName = self.inputNodes[i]
            # get the corresponding node in the instance
            if connName in nodedict:
                conn = nodedict[connName]
                # set the input connector's data ready for its perform() to copy
                # into the outputin
                logger.debug(f"SETTING OUTPUT IN CONNECTOR {conn} TO {data}")
                conn.datum = data
            else:
                logger.debug(f"Looking for {connName}")
                logger.debug(f"Keys are {nodedict.keys()}")
                pcot.ui.error("cannot find input node in instance graph of macro")

        # 3 - run the macro. You might think you could do this by just running the inputs
        # as you set them (recursively running their children) but that would omit non-input
        # root nodes.
        logger.debug("PERFORMING MACRO")
        node.instance.graph.performNodes()

        # 3a - if there's a sink, copy the data to the instance node. Also check node error states,
        # and report (hopefully there will only be one!)
        for n in node.instance.graph.nodes:
            if n.type.name == "sink":
                node.sinkimg = n.img.copy()
                node.sinkimg.setMapping(node.mapping)
            if n.error is not None:
                node.error = n.error

        # 4 - copy the output from the output connectors nodes into the node's outputs
        for i in range(0, len(node.outputs)):
            # get the output connector name
            connName = self.outputNodes[i]
            # get the corresponding node in the instance
            if connName in self.outputNodes:
                conn = nodedict[connName]
                # the output connector will have set its data field to its input
                # set the node's output to that data
                node.setOutput(i, conn.datum)
            else:
                pcot.ui.error("cannot find output node in instance graph of macro")


class TabMacro(Tab):
    """this is the UI for macros, and it should probably not be here."""
    def __init__(self, node: XFormMacro, w):
        super().__init__(w, node, 'tabmacro.ui')
        self.w.openProto.clicked.connect(self.openProto)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)
        self.w.canvas.setPersister(node)
        self.nodeChanged()

    def openProto(self):
        if self.node.instance is not None:
            pcot.ui.mainwindow.MainUI(self.node.graph.doc,
                                      macro=self.node.instance.proto,
                                      doAutoLayout=False)

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)

        self.w.canvas.display(self.node.sinkimg)


class TabConnector(Tab):
    """the UI for macro connectors"""
    def __init__(self, node, w):
        super().__init__(w, node, 'tabconnector.ui')
        self.w.variant.changed.connect(self.variantChanged)
        self.nodeChanged()

    def onNodeChanged(self):
        # set the current type
        i = Datum.types.index(self.node.conntype)
        if i < 0:
            raise Exception('unknown connector type: {}'.format(self.node.conntype))
        self.w.variant.set(self.node.conntype)

    def variantChanged(self, t):
        self.node.conntype = t
        self.node.proto.setConnectors()
