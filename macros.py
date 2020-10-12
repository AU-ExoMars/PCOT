import xform
from xform import XFormType
import ui,conntypes

# a macro consists of a graph and links to any macro instances,
# so that changes in the prototype can be reflected in the instances.

class MacroPrototype:
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
# For that readson they are not decorated with @xformtype.


class XFormMacroIn(XFormType):
    def __init__(self):
        super().__init__(self,name,"in","macroconnect","0.0.0")
        self.addOutputConnector("","any")
        

class XFormMacroOut(XFormType):
    def __init__(self):
        super().__init__(self,name,"out","macroconnect","0.0.0")
        self.addInputConnector("","any")

