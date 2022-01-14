from pcot.datum import Datum
from pcot.xform import xformtype, XFormType


@xformtype
class XFormDisplayVal(XFormType):
    """Display a numeric value inside the node's box in the graph"""
    def __init__(self):
        super().__init__("show number", "maths", "0.0.0")
        self.addInputConnector("", Datum.NUMBER)

    def createTab(self, n, w):
        return None

    def perform(self, node):
        val = node.getInput(0, Datum.NUMBER)
        node.displayName = str(val)
