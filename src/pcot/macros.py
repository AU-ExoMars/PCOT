"""Code dealing with macros and macro prototypes"""
import logging
from collections import Counter
from typing import List, OrderedDict, Optional

from PySide2.QtWidgets import QVBoxLayout

import pcot.ui.mainwindow
import pcot.xform as xform
from pcot import datum
from pcot.datum import Datum
from pcot.imagecube import ChannelMapping
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType, TaggedVariantDictType, TaggedDict
from pcot.ui.tabs import Tab
from pcot.ui.taggedaggregates import AggregateEditorDialog, AggregateEditorWidget
from pcot.utils import deb
from pcot.xform import XFormType, XFormGraph

logger = logging.getLogger(__name__)

# this is the TaggedDictType which defines a macro parameter (i.e. the XMacroParam node).
# Because the AggregateEditorWidget can only really handle tagged dicts, we need this to be a TD at the top
# level. This level gets hidden in the editor - it's an ugly hack.

FLOATPARAMTYPE = TaggedDictType(
    ptype=("type",str,"float",["float","int"]),
    desc=("description",str,""),
    min=("min",float,0),
    max=("max",float,10),
    default=("default",float, 0),
)

INTPARAMTYPE = TaggedDictType(
    ptype=("type",str,"int",["float","int"]),
    desc=("description",str,""),
    min=("min",int,0),
    max=("max",int,10),
    default=("default",int,0),
)

PARAMETERTYPE = TaggedDictType(     # see comment above for why the variant is wrapped like this.
    variant=("variant", TaggedVariantDictType(
    "ptype",
    {
        "float": FLOATPARAMTYPE,
        "int": INTPARAMTYPE,
    },
    default_type_name="float"),None))


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
        # self.proto.graph.dump()
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
        self.params = TaggedDictType()  # no parameters

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
        self.params = TaggedDictType() # no params

    def perform(self, node):
        """perform stores its input in its data field, ready for XFormMacro.perform() to read it"""
        if node.getInputType(0) == Datum.VARIANT:
            raise xform.XFormException('TYPE', 'input type of macro output node must be specified')
        node.datum = node.getInput(0)
        logger.debug(f"DUMP OF OUTCONNECTOR {node.name}, {node}")
        if logger.isEnabledFor(logging.DEBUG):
            node.dump()
        logger.debug(f"CONNECTOR OUTPUT {node.datum}")


@xform.xformtype
class XFormMacroParam(XFormMacroConnector):
    """A parameter for a macro; or rather a connector for one. The displayName of the node is the name of the parameter
    and should be set by the creating method"""
    def __init__(self):
        super().__init__("param")
        self.addOutputConnector("", Datum.VARIANT)
        self.params = PARAMETERTYPE
        self.autoserialise = tuple()    # otherwise we autoserialise idx, and we don't have one.

    def init(self, node):
        # the initial value is just 0.0
        super().init(node)
        print(f"NODE INIT {node}")
        node.datum = Datum.k(0)

    def perform(self, node):
        """perform sets the output to the value stored in the parameter, which is done in the macro's perform."""
        node.setOutput(0, node.datum)
        logger.debug(f"DUMP OF PARAMCONNECTOR {node.name}, {node}")
        if logger.isEnabledFor(logging.DEBUG):
            node.dump()
        logger.info(f"PARAM OUTPUT for {node} - {node.datum.get(Datum.NUMBER).n}")

    def onRemove(self, node):
        node.proto.paramChanged(node)

    def createTab(self, node, window):
        """create the edit tab"""
        return TabMacroParam(node, window)


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

    ## a TDT defining the parameters, regenerated when parameters are added, removed
    # or change (not the values, though!). None if there aren't any. The actual
    # parameter VALUES are stored in the instances!
    parameter_definitions: TaggedDictType

    def __init__(self, doc, name=None, data=None):
        """initialise, creating a new unique name if none provided. Will also deserialise a
        prototype graph and parameter definitions if serialised data is required (used when
        deserialising a document)"""
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

        # initialise the parameter data
        self.parameter_definitions = TaggedDictType()

        if data:
            # if we are deserialising, do that for the graph
            self.graph.deserialise(data, True)
            # then iterate over the graph to find the parameters and build
            # the parameter_definitions.
            self.paramChanged(None)

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
        node.parameters = self.parameter_definitions.create()  # create the params
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
            elif n.type.name == 'param':
                n.outputTypes[0] = n.conntype
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
        self.name = newname
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
        """serialise an individual macro instance node by storing the macro name.
        Macros themselves are just graphs and are serialised in the Document serialiser."""
        if node.instance is not None:
            name = node.instance.proto.name
        else:
            name = None
        return {'proto': name,
                'parameters': node.parameters.serialise(forceUnordered=True)
                }

    def deserialise(self, node, d):
        """deserialise an individual macro instance node by dereferencing the macro
        name and creating a new MacroInstance. See "serialise" above for how the actual macro
        is serialised."""

        name = d['proto']
        doc = node.graph.doc
        if name is None:
            node.instance = None
        else:
            if name in doc.macros:
                MacroInstance(doc.macros[name], node)
            else:
                pcot.ui.error("Cannot find macro {} in internal dict".format(name))
        if 'parameters' in d:
            # this should work, because the macro's parameter_definitions will have been
            # created when the macro is loaded.
            node.parameters = self.parameter_definitions.deserialise(d['parameters'])


    @staticmethod
    def deleteMacro(xformtype):
        """delete a macro"""
        # delete all instances
        toRebuild = set()
        # the node instances will only have an entry for this type if there are nodes present, I believe.
        if xformtype in xformtype.doc.nodeInstances:
            for x in xformtype.doc.nodeInstances[xformtype]:
                x.graph.remove(x)
                toRebuild.add(x.graph)
            for x in toRebuild:
                x.rebuildGraphics()
            del xformtype.doc.nodeInstances[xformtype]
        # and now the macro itself from the doc
        del xformtype.doc.macros[xformtype.name]
        # caller rebuilds palettes

    def createTab(self, n, w):
        """creates edit tab for an instance"""
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

        # 2 - copy the parameter values into the parameter nodes
        for n in node.instance.graph.nodes:
            if n.type.name == "param":
                print(f"node param in XFormMacro perform; {n} {n.displayName} = {node.parameters[n.displayName]}")
                n.datum = Datum.k(node.parameters[n.displayName])
                print(f"datum is; {n.datum}")


        # 3 - run the macro. You might think you could do this by just running the inputs
        # as you set them (recursively running their children) but that would omit non-input
        # root nodes.
        logger.debug("PERFORMING MACRO")
        node.instance.graph.performNodes()

        # 3a - if there's a sink, copy the data to the instance node. Also check node error states,
        # and report (hopefully there will only be one!)
        for n in node.instance.graph.nodes:
            if n.type.name == "sink":
                if n.data and n.data.tp == Datum.IMG:
                    node.sinkimg = n.data.get(Datum.IMG)
                    node.sinkimg.setMapping(node.mapping)
                else:
                    node.sinkimg = None
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

    def getHelpText(self):
        """Get the help text for this macro by looking for a DOC comment"""
        hdr = "### Macro node\n\n"
        for x in self.graph.nodes:
            if x.type.name == "comment":
                s = x.params.string
                if s.startswith("DOC "):
                    return hdr+s[4:]
        return hdr+"This is a macro - to add help, create a comment node in the prototype and start the text with 'DOC '"

    def paramChanged(self, paramNode):
        """A parameter has changed. We need to recreate the TDT defining the parameters from the parameter nodes."""
        print("rebuilding params")
        tdd_def = {}
        # recreate the TDT for parameters from the TDs in the parameter nodes
        for x in filter(lambda x: x.type.name == "param", self.graph.nodes):
            d = x.params.variant.get()  # get the "child" dict defining the parameter
            if d.ptype == "int":
                item = (d.desc, int, d.default, [d.min,d.max])
            elif d.ptype == "float":
                item = (d.desc, float, d.default, [d.min,d.max])
            else:
                raise Exception(f"Unknown parameter type {d.ptype}")

            print(f"  Found parameter node {x}, item is {item}")
            tdd_def[x.displayName] = item
        # ensure alphabetical order
        tdd_def = dict(sorted(tdd_def.items()))
        # and build the new TDD
        self.parameter_definitions = TaggedDictType(**tdd_def)

        # now the "fun" part - we need to update all the parameter VALUES
        # to match the new TDD, inside each instance of the macro
        for instance in self.getInstances():
            print(f"  Found instance node {instance}")
            # This needs to firstly remove any parameters from the TD
            # that no longer exist in the TDT, then add parameters which
            # are new. This is probably done most easily by creating an
            # entirely new TD and copying items over that are present in the new
            # TD from the old one (overwriting them). We check ranges and
            # convert types too.
            td = self.parameter_definitions.create()
            # Now any new items will have been created, but we have to copy the old
            # items in and attempt to correct their data. THIS CODE HEAVILY ASSUMES
            # ALL PARAMS ARE NUMERIC.
            if instance.parameters:
                for k,v in instance.parameters.items():
                    if k in td.keys():
                        # this item exists in the new TD and its value
                        # should be copied from the old.
                        tag = td.tag(k)
                        v = instance.parameters[k] # get he old val we need to check
                        # check it's in bounds and clip if not (bounds may have changed)
                        if isinstance(tag.valid_choices, tuple|list):
                            mn, mx = tag.valid_choices
                            v = min(max(v, mn), mx)
                        # and convert type (which may also have changed)
                        if tag.type == int:
                            v = int(v)
                        elif tag.type == float:
                            v = float(v)
                        # OK.
                        td[k] = v
                        print(td[k])
            instance.parameters = td    # and replace the params.
            print(f" instance parameters are {td.as_dict()}")

            # update all the open tabs for this instance
            for tab in instance.tabs:
                if isinstance(tab, TabMacro):
                    tab.updateParameters()




class TabMacro(Tab):
    """this is the UI for macro instances, and it should probably not be here."""
    def __init__(self, node: XFormMacro, w):
        super().__init__(w, node, 'tabmacro.ui')
        self.w.openProto.clicked.connect(self.openProto)
        # create editor for the instance's parameter values
        self.paramLayout = QVBoxLayout()
        self.w.paramBox.setLayout(self.paramLayout)
        self.updateParameters()
        self.w.canvas.setNode(node)
        self.nodeChanged()

    def updateParameters(self):
        """Update the parameter widget for this instance or create a new one."""
        if old := self.paramLayout.takeAt(0):
            old.widget().deleteLater()
        paramEditor = AggregateEditorWidget(self.node.parameters, internal_editor=True, handler=self)
        self.paramLayout.addWidget(paramEditor)


    def onPreChange(self,editor):
        pass

    def onPostChange(self,editor):
        print(f"a param has changed value {self.node.parameters.as_dict()}")
        self.changed()


    def openProto(self):
        if self.node.instance is not None:
            pcot.ui.mainwindow.MainUI(self.node.graph.doc,
                                      macro=self.node.instance.proto,
                                      doAutoLayout=False)

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setNode(self.node)
        self.w.canvas.display(self.node.sinkimg)


class TabConnector(Tab):
    """the UI for macro connectors"""
    def __init__(self, node, w):
        super().__init__(w, node, 'tabconnector.ui')

        # make the widget show only appropriate types. TODO -refactor away
        self.w.variant.setMode(mode='connector')
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


class TabMacroParam(Tab):
    """the UI for macro parameters"""
    def __init__(self, node, w, parameter=False):
        super().__init__(w, node, 'tabmacroparam.ui')
        # top level always has to be a TaggedDict, so we have one with only one key. Ugh.
        self.editor = AggregateEditorWidget(node.params, suppress_single_key_label=True, internal_editor=True,
                                            handler=self)
        self.w.widget.layout().addWidget(self.editor)
        self.nodeChanged()

    def onPostChange(self, editor):
        # this should mirror any change in the editor to the node data. Really, it needs to inform the
        # entire macro prototype that the parameter set has changed.
        self.node.proto.paramChanged(self.node)
        # we don't really need to call changed here - we only need to do that if the parameters
        # have actually changed their values. That's actually quite hard to check for my little
        # head at the moment.
        self.changed()

    def onNodeChanged(self):
        # make the editor reflect the node
        d = self.node.params.variant.get()  # get the "child" dict
        # set the conntype accordingly
        if d.ptype == "int" or d.ptype == "float":
            # this should always happen, these are the only two types we support.
            self.node.conntype = Datum.NUMBER
            self.node.setError(None)
        else:
            self.node.conntype = Datum.VARIANT
            self.node.setError(xform.XFormException('DATA', "bad param type"))
        self.node.proto.setConnectors()