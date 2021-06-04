import pcot.conntypes as conntypes
from pcot.xform import xformtype, XFormType


@xformtype
class XFormDisplayVal(XFormType):
    """Display a numeric value inside the node's box in the graph"""
    def __init__(self):
        super().__init__("show number", "maths", "0.0.0")
        self.addInputConnector("", conntypes.NUMBER)

    def createTab(self, n, w):
        return None

    def perform(self, node):
        val = node.getInput(0, conntypes.NUMBER)
        node.displayName = str(val)
