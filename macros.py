import xform
from xform import XFormType
import ui,conntypes
from typing import List, Set, Dict, Tuple, Optional, Any, OrderedDict, ClassVar


# annoying forward decls for type hints
class MacroInstance: 
    pass
class MacroPrototype: 
    pass
class XFormMacro:
    pass

# a macro consists of a graph and links to any macro instances,
# so that changes in the prototype can be reflected in the instances.
# It also contains its own XFormType object, based on XFormMacro
# but with a unique name and different connectors.

class MacroPrototype:

    protos: ClassVar[Dict[str,MacroPrototype]]  # dictionary of all macros by name
    counter: ClassVar[int]                      # counter for macros for naming

    name: str                                   # prototype's unique name
    graph: xform.XFormGraph                     # the graph for this prototype
    instances: List[MacroInstance]              # list of all my instances
    type: XFormMacro                            # the node type object
    
    protos = {} # dictionary of all macro prototypes
    counter= 0  # counter for new prototypes
    def __init__(self,name=None):
        # create our graph and name
        self.graph = xform.XFormGraph()
        if name is None:
            name = "untitled{}".format(MacroPrototype.counter)
            MacroPrototype.counter+=1
        # ensure unique name
        if name in MacroPrototype.protos:
            raise Exception("macro {} already exists".format(name))
        self.name = name
        # we have no instances
        self.instances=[]
        # register with the class dictionary
        MacroPrototype.protos[name]=self
        # create a new XFormType object
        self.type = XFormMacro(name)
    
    # used when the number of connectors has changed - we
    # need to change the connectors on the macro block used in other
    # graphs by updating the type object. 
    def setConnectors(self):
        inputs=0
        outputs=0
        for n in self.graph.nodes:
            if n.type.name=='in':
                inputs+=1
            elif n.type.name=='out':
                outputs+=1
        self.type.setConnectors(inputs,outputs)

    @staticmethod
    def serialiseAll():
        d={}
        for k,v in MacroPrototype.protos.items():
            d[k] = v.graph.serialise()
        return d
        
    @staticmethod
    def deserialiseAll(d):
        for k,v in d.items():
            p = MacroPrototype(k)
            p.graph.deserialise(v,True)
            MacroPrototype.protos[k] = p
        
        
# This is the instance of a macro, containing its copy of the graph
# and some metadata

class MacroInstance:
    def __init__(self,proto):
        self.proto=proto
        self.graph = xform.XFormGraph() # create an empty graph
        self.copyProto() # copy the graph from the prototype
        proto.instances.append(self)

    # this serialises and then deserialises the prototype's
    # graph, giving us a fresh copy of the nodes.
    def copyProto(self):
        d = self.proto.graph.serialise()
        self.graph.deserialise(d,True)


# these are the connections for macros, which should only be added to macros.
# For that readson they are not decorated with @xformtype. However, they do
# get added to allTypes.
#
# Additional fields:
# - proto points to the containing MacroPrototype

class XFormMacroIn(XFormType):
    def __init__(self):
        super().__init__("in","hidden","0.0.0")
        self._md5='' # we ignore the MD5 checksum for versioning
        self.addOutputConnector("","any")
        

class XFormMacroOut(XFormType):
    def __init__(self):
        super().__init__("out","hidden","0.0.0")
        self._md5='' # we ignore the MD5 checksum for versioning
        self.addInputConnector("","any")
        

# register them
XFormMacroIn()
XFormMacroOut()


# the actual macro xform type - this doesn't get autoregistered
# because a new one is created for each individual macro prototype.

class XFormMacro(XFormType):
    """Encapsulates an instance of a macro"""
    
    def __init__(self,name):
        super().__init__(name,"utility","0.0.0")
        self._md5='' # we ignore the MD5 checksum for versioning
        self.hasEnable=True
        # initialise the (empty) connectors and will also add us to
        # the palette
        self.setConnectors(0,0)
        
    def createTab(self,n,w):
        return TabMacro(n,w)
        
    def init(self,node):
        node.instance = None
        
    def setConnectors(self,ins,outs):
        # modify the outputs
        self.inputConnectors = [ ('','any','macro input') for x in range(0,ins)]
        self.outputConnectors = [ ('','any','macro output') for x in range(0,outs)]
        # and we're also going to have to rebuild the palette, so inform all main
        # windows
        ui.mainwindow.MainUI.rebuildPalettes()
        # and rebuild absolutely everything
        ui.mainwindow.MainUI.rebuildAll()
        for n in self.instances:
            n.connCountChanged()

    def remove(self,node):
        super().remove(node)
        if node.instance is not None:
            node.instance.proto.instances.remove(node.instance)
                
        
        
    def serialise(self,node):
        if node.instance is not None:
            name = node.instance.proto.name
        else:
            name = None
        return {'proto': name}

    def deserialise(self,node,d):
        name = d['proto']
        if name is None:
            node.instance = None
        else:
            if name in MacroPrototype.protos:
                node.instance = MacroInstance(MacroPrototype.protos[name])
                ui.error("Macro instantiated, need to update connections")
            else:
                ui.error("Cannot find macro {} in internal dict".format(name))
        
    def perform(self,node):
        pass

# this is the UI for macros, and it should probably not be here.
        
class TabMacro(ui.tabs.Tab):
    def __init__(self,node,w):
        super().__init__(w,node,'assets/tabmacro.ui')
        self.w.macro.currentIndexChanged.connect(self.macroChanged)
        self.w.openProto.pressed.connect(self.openProto)
        # populate the combobox
        for x in MacroPrototype.protos:
            self.w.macro.addItem(x)
        self.onNodeChanged()
        
    def openProto(self):
        if self.node.instance is not None:
                w=ui.mainwindow.MainUI.createMacroWindow(self.node.instance.proto,False)
            
    def macroChanged(self,i):
        name = self.w.macro.itemText(i)
        if name in MacroPrototype.protos:
            self.node.instance = MacroInstance(MacroPrototype.protos[name])
            ui.error("Macro instantiated, need to update connections")
        else:
            ui.error("Cannot find macro {} in internal dict".format(name))        

    def onNodeChanged(self):
        # set the selected macro to the one which matches our name
        if self.node.instance is not None:
            i = self.w.macro.findText(self.node.instance.proto.name)
            if i<0:
                ui.error("Can't find macro {} in macro combobox!".format(self.node.instance.proto.name))
            else:
                self.w.macro.setCurrentIndex(i)
