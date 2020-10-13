import xform
from xform import XFormType
import ui,conntypes
from typing import List, Set, Dict, Tuple, Optional, Any, OrderedDict, ClassVar

# annoying forward decls for type hints
class MacroInstance: 
    pass
class MacroPrototype: 
    pass

# a macro consists of a graph and links to any macro instances,
# so that changes in the prototype can be reflected in the instances.

class MacroPrototype:

    protos: ClassVar[Dict[str,MacroPrototype]]  # dictionary of all macros by name
    counter: ClassVar[int]                      # counter for macros for naming

    name: str                                   # prototype's unique name
    graph: xform.XFormGraph                     # the graph for this prototype
    instances: List[MacroInstance]              # list of all my instances
    
    protos = {} # dictionary of all macro prototypes
    counter= 0  # counter for new prototypes
    def __init__(self,name=None):
        self.graph = xform.XFormGraph()
        if name is None:
            name = "untitled{}".format(MacroPrototype.counter)
            MacroPrototype.counter+=1
        self.name = name
        self.instances=[]
        MacroPrototype.protos[name]=self
    
    # used when the number of connectors has changed - we
    # need to change the connectors on the macro block used in other
    # graphs    
    def setConnectors(self):
        inputs=0
        outputs=0
        for n in self.graph.nodes:
            if n.type.name=='in':
                inputs+=1
            elif n.type.name=='out':
                outputs+=1
        raise Exception("SET CONNECTORS")                
    

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
        self.addOutputConnector("","any")
        

class XFormMacroOut(XFormType):
    def __init__(self):
        super().__init__("out","hidden","0.0.0")
        self.addInputConnector("","any")

# register them
XFormMacroIn()
XFormMacroOut()
