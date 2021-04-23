from PyQt5 import QtWidgets

import pcot.conntypes as conntypes
import pcot.ui.tabs
from pcot.utils import ops
from pcot.utils.ops import BinopException
from pcot.xform import xformtype, XFormType, XFormException


class XFormBinop(XFormType):

    def __init__(self, name):
        super().__init__(name, "maths", "0.0.0")
        self.addInputConnector("", conntypes.ANY)
        self.addInputConnector("", conntypes.ANY)
        self.addOutputConnector("", conntypes.VARIANT)

    def createTab(self, n, w):
        return TabBinop(n, w)

    def init(self, node):
        pass

    def perform(self, node):
        a = node.getInput(0)
        b = node.getInput(1)

        try:
            res = ops.binop(a, b, self.op, node.getOutputType(0))
        except BinopException as be:
            raise XFormException('DATA','Math error: {}'.format(be))
        if res is not None and res.isImage():
            res.val.setMapping(node.mapping)
            node.img = res.val
        else:
            node.img = None
        print("{} : inputs {} {}, output {} ".format(node.displayName, a, b, res))
        node.setOutput(0, res)


@xformtype
class XFormAdd(XFormBinop):
    def __init__(self):
        super().__init__("add")
        self.op = lambda x, y: x + y


@xformtype
class XFormSub(XFormBinop):
    def __init__(self):
        super().__init__("subtract")
        self.op = lambda x, y: x - y


@xformtype
class XFormMul(XFormBinop):
    def __init__(self):
        super().__init__("multiply")
        self.op = lambda x, y: x * y


@xformtype
class XFormDiv(XFormBinop):
    def __init__(self):
        super().__init__("divide")
        self.op = lambda x, y: x / y


class TabBinop(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabbinop.ui')
        self.w.variant.setTitle("Output type")
        self.w.variant.changed.connect(self.variantChanged)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)
        self.onNodeChanged()

    def onNodeChanged(self):
        self.w.variant.set(self.node.getOutputType(0))
        self.w.canvas.display(self.node.img)

    def variantChanged(self, t):
        self.node.outputTypes[0] = t
        self.node.graph.ensureConnectionsValid()
        self.changed()
