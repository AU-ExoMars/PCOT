import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage

# Simple data dumper: just prints a string of its output
# into its window

@xformtype
class XFormDump(XFormType):
    """Simple data dump: prints a string of its output into its window"""
    def __init__(self):
        super().__init__("dump","data","0.0.0")
        self.addInputConnector("any","any")
        
    def createTab(self,n,w):
        return TabDump(n,w)
        
    def init(self,node):
        node.data = None
        node.tp = "unconnected"
        
    def perform(self,node):
        d = node.getInput(0)
        if d is None:
            node.tp = "unconnected"
            node.data = "None"
        else:
            node.tp = d.tp
            node.data = str(d.val)


class TabDump(ui.tabs.Tab):
    def __init__(self,node,w):
        super().__init__(w,node,'assets/tabdump.ui')
        self.onNodeChanged()
        
    def onNodeChanged(self):
        self.w.type.setPlainText(self.node.tp)
        self.w.text.setPlainText(str(self.node.data))
