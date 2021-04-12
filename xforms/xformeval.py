import conntypes
import ui.tabs
from expressions.eval import Parser
from xform import XFormType, xformtype, XFormException


@xformtype
class XFormEval(XFormType):
    def __init__(self):
        super().__init__("eval", "maths", "0.0.0")
        self.parser = Parser()
        self.addInputConnector("a", conntypes.ANY)
        self.addInputConnector("b", conntypes.ANY)
        self.addInputConnector("c", conntypes.ANY)
        self.addInputConnector("d", conntypes.ANY)
        self.addOutputConnector("", conntypes.VARIANT)

    def createTab(self, n, w):
        return TabEval(n, w)

    def init(self, node):
        node.expr = ""

    def perform(self, node):
        self.parser.registerVar('a', lambda: node.getInput(0))
        self.parser.registerVar('b', lambda: node.getInput(1))
        self.parser.registerVar('c', lambda: node.getInput(2))
        self.parser.registerVar('d', lambda: node.getInput(3))

        try:
            if len(node.expr.strip()) > 0:
                res = self.parser.run(node.expr)
                node.setOutput(0, res)
        except Exception as e:
            raise XFormException('EXPR', str(e))


class TabEval(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabeval.ui')
        self.w.variant.setTitle("Output type")
        self.w.run.clicked.connect(self.run)
        self.w.expr.setPlaceholderText('insert expression and click Run')
        self.w.expr.textChanged.connect(self.exprChanged)
        self.w.variant.changed.connect(self.variantChanged)
        self.onNodeChanged()

    def variantChanged(self, t):
        self.node.outputTypes[0] = t
        self.node.graph.ensureConnectionsValid()
        self.changed()

    def exprChanged(self):
        self.node.expr = self.w.expr.toPlainText()
        # don't call changed() or we'll run the expr on every key press!

    def run(self):
        self.changed()

    def onNodeChanged(self):
        self.w.variant.set(self.node.getOutputType(0))
