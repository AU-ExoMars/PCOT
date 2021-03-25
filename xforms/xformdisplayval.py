import conntypes
from xform import xformtype, XFormType


@xformtype
class XFormDisplayVal(XFormType):
    """Display a numeric value inside the node's box in the graph"""
    def __init__(self):
        super().__init__("show number", "maths", "0.0.0")
        self.addInputConnector("", "number")

    def createTab(self, n, w):
        return None

    def perform(self, node):
        val = node.getInput(0, conntypes.NUMBER)
        node.displayName = str(val)
