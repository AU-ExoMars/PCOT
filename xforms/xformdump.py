import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage

# Simple data dumper: just prints a string of its output
# into its window

@xformtype
class XFormDump(XFormType):
    """Simple data dump: prints a string of its output into its window"""
    def __init__(self):
        super().__init__("dump","0.0.0")
        self.addInputConnector("any","any")
        
    def createTab(self,n):
        return TabDump(n)
        
    def init(self,node):
        node.data = None
        node.tp = "unconnected"
        
    def perform(self,node):
        # copy the input
        node.data = node.getInput(0)
        # but now we want to know the actual type. We hack into the model a bit here.
        x = node.inputs[0]
        if x is not None:
            n,i = x
            node.tp = n.getOutputType(i)
        else:
            node.tp = "unconnected"
        
class TabDump(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabdump.ui')
        self.onNodeChanged()
        
    def onNodeChanged(self):
        self.w.type.setPlainText(self.node.tp)
        self.w.text.setPlainText(str(self.node.data))
