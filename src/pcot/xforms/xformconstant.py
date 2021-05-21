from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

import pcot.conntypes as conntypes
import pcot.ui as ui
from pcot.xform import xformtype, XFormType

validKeys = {Qt.Key_0, Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4, Qt.Key_5, Qt.Key_6, Qt.Key_7, Qt.Key_8, Qt.Key_9,
             Qt.Key_Period, Qt.Key_Minus,
             Qt.Key_Delete, Qt.Key_Backspace, Qt.Key_Left, Qt.Key_Right}


## text in middle of main rect and on connections
class GNumberText(QtWidgets.QGraphicsTextItem):
    def __init__(self, parent, node):
        super().__init__(str(node.val), parent=parent)
        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.setTextWidth(50)
        self.setTabChangesFocus(True)
        self.node = node

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        print("Focus lost")
        self.setPlainText(str(self.node.val))
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # return means "go!"
        if event.key() == Qt.Key_Return:
            try:
                v = self.toPlainText()
                self.node.val = float(v)
                self.clearFocus()
                # we also have to tell the graph to perform from here
                self.node.graph.performNodes(self.node)
            except ValueError:
                ui.error("cannot convert text")
            event.accept()
        # Ignore non-numeric
        elif event.key() not in validKeys:
            event.accept()
        else:
            super().keyPressEvent(event)

    def setColour(self, col):
        pass


@xformtype
class XFormConstant(XFormType):
    """Generates a numeric value which can be typed directly into the node's box in the graph"""
    def __init__(self):
        super().__init__("constant", "maths", "0.0.0")
        self.addOutputConnector("", conntypes.NUMBER)
        self.autoserialise = ('val',)

    ## build the text element of the graph scene object for the node. By default, this
    # will just create static text, but can be overridden.
    @staticmethod
    def buildText(n):
        x, y = n.xy
        text = GNumberText(n.rect, n)
        text.setPos(x + ui.graphscene.XTEXTOFFSET, y + ui.graphscene.YTEXTOFFSET + ui.graphscene.CONNECTORHEIGHT)
        return text

    def createTab(self, n, w):
        return None

    def init(self, node):
        node.val = 0

    def perform(self, node):
        node.setOutput(0, conntypes.Datum(conntypes.NUMBER, node.val))
