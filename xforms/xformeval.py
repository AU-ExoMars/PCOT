import conntypes
import ui.tabs
from xform import XFormType, xformtype


@xformtype
class XFormEval(XFormType):
    def __init__(self):
        super().__init__("eval", "maths", "0.0.0")
        self.addInputConnector("a", conntypes.ANY)
        self.addInputConnector("b", conntypes.ANY)
        self.addInputConnector("c", conntypes.ANY)
        self.addInputConnector("d", conntypes.ANY)
        self.addOutputConnector("", conntypes.VARIANT)

    def createTab(self, n, w):
        return TabEval(n, w)

    def init(self, node):
        pass

    def perform(self, node):
        a = node.getInput(0)
        b = node.getInput(1)
        c = node.getInput(2)
        d = node.getInput(3)

        res = None
        node.setOutput(0, res)


class TabEval(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabeval.ui')
        self.w.variant.setTitle("Output type")
        self.w.variant.changed.connect(self.variantChanged)
        self.onNodeChanged()

    def variantChanged(self, t):
        self.node.outputTypes[0] = t
        self.node.graph.ensureConnectionsValid()
        self.changed()

    def onNodeChanged(self):
        self.w.variant.set(self.node.getOutputType(0))

