import cv2 as cv
import numpy as np
from PyQt5 import QtGui, QtWidgets

import conntypes
import ui.number
import ui.tabs
from pancamimage import ImageCube
from utils import binop
from xform import xformtype, XFormType, XFormException, Datum


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

        res = binop.binop(a, b, self.op, node.getOutputType(0))
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


class TabBinop(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabbinop.ui')
        # populate with types
        layout = QtWidgets.QVBoxLayout()
        self.buttons = []
        idx = 0
        for x in conntypes.types:
            b = QtWidgets.QRadioButton(x)
            layout.addWidget(b)
            self.buttons.append(b)
            b.idx = idx
            idx += 1
            b.toggled.connect(self.buttonToggled)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)
        self.w.type.setLayout(layout)
        self.onNodeChanged()

    def onNodeChanged(self):
        # set the current type
        i = conntypes.types.index(self.node.getOutputType(0))
        self.buttons[i].setChecked(True)
        self.w.canvas.display(self.node.img)

    def buttonToggled(self, checked):
        for b in self.buttons:
            if b.isChecked():
                self.node.outputTypes[0] = conntypes.types[b.idx]
                self.node.graph.ensureConnectionsValid()
                self.changed()
                break
