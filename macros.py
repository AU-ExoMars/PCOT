## @package macros
# Code dealing with macros and macro prototypes

import xform
from xform import XFormType
import ui,conntypes
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from typing import List, Set, Dict, Tuple, Optional, Any, OrderedDict, ClassVar

## This is the instance of a macro, containing its copy of the graph
# and some metadata

class MacroInstance:
    ## @var proto
    # The XFormMacro object which is the macro prototype
    ## @var node
    # The XForm node which holds this macro instance
    ## @var graph
    # The XFormGraph which is this instance of the macro - not to be confused
    # with the macro's prototype graph, which is stored in proto.graph.
    
    ## construct, taking the XFormMacro prototype object and the XForm I am inside.
    def __init__(self,proto,node):
        self.proto=proto
        self.node=node # backpointer to the XForm containing me
        self.graph = xform.XFormGraph(False) # create an empty graph, not a macro prototype
        self.copyProto() # copy the graph from the prototype

    ## this serialises and then deserialises the prototype's
    # graph, giving us a fresh copy of the nodes. However, the UUID "names"
    # are the same so that corresponding nodes in instance and copy
    # have the same UUID (not really "U", but you get the idea)
    def copyProto(self):
        d = self.proto.graph.serialise()
        self.graph.deserialise(d,True)



## these are the connections for macros, which should only be added to macros.
# For that reason they are not decorated with @xformtype. However, they do
# get added to allTypes.
#
# Additional fields in the XForms:
# - proto points to the containing XFormMacro
# - idx indexes the connector
# - conntype is the type of the connection (a string)

class XFormMacroConnector(XFormType):
    def __init__(self,name):
        super().__init__(name,"hidden","0.0.0")
        self.displayName = '??' # forces a rename in setConnectors first time
        self._md5='' # we ignore the MD5 checksum for versioning
        self.autoserialise=('idx','conntype')

    ## called from XForm.serialise, saves the macro name
    def serialise(self,node):
        return {'macro':node.proto.name}
        
    ## called from XForm.deserialise, finds the macro
    def deserialise(self,node,d):
        name = d['macro']
        if not name in XFormMacro.protos:
            raise Exception('macro {} not found'.format(name))
        node.proto = XFormMacro.protos[name]
        node.proto.setConnectors()
    
    ## when connectors are removed, the prototype's connectors must change (and
    # thus those of all the instances)
    def remove(self,node):
        node.proto.setConnectors()

    ## force renaming of connectors on instance nodes and in the prototype        
    def rename(self,node,name):
        super().rename(node,name)
        node.proto.setConnectors() # forces rename of connectors on instance nodes

    ## create the edit tab
    def createTab(self,node,window):
        return TabConnector(node,window)
        
## The macro input connector (used inside macro prototypes)    
class XFormMacroIn(XFormMacroConnector):
    def __init__(self):
        super().__init__("in")
        self.addOutputConnector("","any")
        self.addInputConnector("","any")
        

## The macro output connector (used inside macro prototypes)    
class XFormMacroOut(XFormMacroConnector):
    def __init__(self):
        super().__init__("out")
        self.addInputConnector("","any")
        self.addOutputConnector("","any")

# register them
XFormMacroIn()
XFormMacroOut()

class XFormMacro(XFormType):
    pass

## the actual macro xform type - this doesn't get autoregistered
# because a new one is created for each individual macro prototype.
# A macro consists of a graph and links to any macro instances,
# so that changes in the prototype can be reflected in the instances.
# It also contains its own XFormType object, based on XFormMacro
# but with a unique name and different connectors.

class XFormMacro(XFormType):
    protos: ClassVar[Dict[str,XFormMacro]]  # dictionary of all macros by name

    ## @var graph
    # the graph for this prototype
    graph: xform.XFormGraph
    
    ## dictionary of all macros by name    
    protos = {} # dictionary of all macro prototypes

    ## initialise, creating a new unique name if none provided.
    def __init__(self,name):
        # generate name if none provided
        if name is None:
            name = XFormMacro.getUniqueUntitledName()
        # superinit
        super().__init__(name,"macros","0.0.0")
        self._md5='' # we ignore the MD5 checksum for versioning
        self.hasEnable=True
        # create our prototype graph 
        self.graph = xform.XFormGraph(True)
        # ensure unique name
        if name in XFormMacro.protos:
            raise Exception("macro {} already exists".format(name))
        # register with the class dictionary
        XFormMacro.protos[name]=self
        # initialise the (empty) connectors and will also add us to
        # the palette
        self.setConnectors()
        
    ## generates a new unique name for this macro. TODO: MAY NOT WORK ON LOAD/RELOAD.
    @staticmethod
    def getUniqueUntitledName():
        ct=0
        while True:
            name='untitled'+str(ct)
            if not name in XFormMacro.protos:
                return name
            ct+=1
        
    ## This creates an instance of the macro by setting the node's instance value to a
    # new MacroInstance. Other aspects of the xform's macro behaviour are, of course,
    # controlled by setting the node's type, which is done elsewhere.
    def init(self,node):
        # create the macro instance (a lot of which could probably be folded into here,
        # but it's like this for historical reasons actually going waaaay back to
        # the 90s).
        # Remember that this is called to create an instance of the XForm type, which in
        # this case is an instance of the macro.
        node.instance = MacroInstance(self,node)
        
    ## Counts the input/output connectors inside the macro and sets the XFormType's
    # inputs and outputs accordingly, finally changing connector counts and types on
    # the instances.
    def setConnectors(self):
        # count input and output connectors. Potential issue: the graphic labelling of
        # the connectors has to match the indices!
        inputs=0
        outputs=0
        self.inputConnectors = []
        self.outputConnectors = []
        # We modify the display name and index of each IO node.
        # We also add it to this type's connectors.
        # The nodes list must be in create order, so that when we do connCountChanged on
        # the instance objects any new nodes get put at the end.
        for n in self.graph.nodes:
            if n.type.name=='in':
                # only rename if name is still "??" (set in ctor)
                if n.displayName == '??':
                    n.displayName = "in "+str(inputs)
                n.idx = inputs
                # set the connector on the macro object
                self.inputConnectors.append((n.displayName,n.conntype,'macro input'))
                # set the connector on the node itself
                n.inputTypes[0] = n.conntype
                n.outputTypes[0] = n.conntype
                inputs+=1
            elif n.type.name=='out':
                if n.displayName == '??':
                    n.displayName = "out "+str(outputs)
                n.idx = outputs
                self.outputConnectors.append((n.displayName,n.conntype,'macro output'))
                n.inputTypes[0] = n.conntype # set the overrides
                n.outputTypes[0] = n.conntype
                outputs+=1
        # rebuild the various connector structures in each instance
        for n in self.instances:
            n.connCountChanged()
        # make sure all connections in the graph are still valid, disconnecting
        # bad ones
        self.graph.ensureConnectionsValid()
        # and we're also going to have to rebuild the palette, so inform all main
        # windows
        ui.mainwindow.MainUI.rebuildPalettes()
        # and rebuild absolutely everything
        ui.mainwindow.MainUI.rebuildAll()
    
    ## renaming a macro - we have to update more things than default XFormType rename
    def renameType(self,newname):
        # rename all instances if their displayName is the same as the old type name
        for x in self.instances:
            if x.displayName == self.name:
                x.displayName = newname
        # do the default
        # then rename in the macro dictionary
        del XFormMacro.protos[self.name]
        super().renameType(newname)
        XFormMacro.protos[newname]=self
    

    ## this serialises all the macro prototypes
    @staticmethod
    def serialiseAll():
        d={}
        for k,v in XFormMacro.protos.items():
            d[k] = v.graph.serialise()
        return d
      
    ## deserialises all macro prototypes  
    @staticmethod
    def deserialiseAll(d):
        for k,v in d.items():
            p = XFormMacro(k)
            p.graph.deserialise(v,True)

    ## serialise an individual macro instance node by storing the macro name
    def serialise(self,node):
        if node.instance is not None:
            name = node.instance.proto.name
        else:
            name = None
        return {'proto': name}

    ## deserialise an individual macro instance node by dereferencing the macro
    # name and creating a new MacroInstance
    def deserialise(self,node,d):
        name = d['proto']
        if name is None:
            node.instance = None
        else:
            if name in XFormMacro.protos:
                MacroInstance(XFormMacro.protos[name],node)
            else:
                ui.error("Cannot find macro {} in internal dict".format(name))
        
    ## creates edit tab
    def createTab(self,n,w):
        return TabMacro(n,w)
        
    ## perform the macro!
    def perform(self,node):
        # 1 - find the input and output connector nodes in the instance graph
        # 2 - copy the inputs from the node's inputs into the input connector nodes
        # 3 - run the macro 
        # 4 - copy the output from the output connectors nodes into the node's outputs

## this is the UI for macros, and it should probably not be here.
        
class TabMacro(ui.tabs.Tab):
    def __init__(self,node,w):
        super().__init__(w,node,'assets/tabmacro.ui')
        self.w.openProto.pressed.connect(self.openProto)
        self.onNodeChanged()
        
    def openProto(self):
        if self.node.instance is not None:
            w=ui.mainwindow.MainUI.createMacroWindow(self.node.instance.proto,False)
 
## the UI for macro connectors
           
class TabConnector(ui.tabs.Tab):
    def __init__(self,node,w):
        super().__init__(w,node,'assets/tabconnector.ui')
        # populate with types
        layout = QtWidgets.QVBoxLayout()
        self.buttons=[]
        idx=0
        for x in conntypes.types:
            b = QtWidgets.QRadioButton(x)
            layout.addWidget(b)
            self.buttons.append(b)
            b.idx = idx
            idx+=1
            b.toggled.connect(self.buttonToggled)
        self.w.type.setLayout(layout)
        self.onNodeChanged()
        
    def onNodeChanged(self):   
        # set the current type
        i = conntypes.types.index(self.node.conntype)
        if i<0:
            raise Exception('unknown connector type: {}'.format(self.node.conntype))
        self.buttons[i].setChecked(True)
        
    def buttonToggled(self,checked):
        for b in self.buttons:
            if b.isChecked():
                self.node.conntype = conntypes.types[b.idx]
                self.node.proto.setConnectors()
                break
