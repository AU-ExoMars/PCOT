import xform
from xform import XFormType
import ui,conntypes

# a macro consists of a graph and links to any macro instances,
# so that changes in the prototype can be reflected in the instances.

class MacroPrototype:
    def __init__(self):
        self.graph = xform.XFormGraph()
        self.instances=[]
        



# these are the connections for macros, which should only be added to macros.
# For that readson they are not decorated with @xformtype.


class XFormMacroIn(XFormType):
    def __init__(self):
        super().__init__(self,name,"in","macroconnect","0.0.0")
        self.addOutputConnector("","any")
        

class XFormMacroOut(XFormType):
    def __init__(self):
        super().__init__(self,name,"in","macroconnect","0.0.0")
        self.addInputConnector("","any")

