from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

import ui
from xform import xformtype, XFormType


## text in middle of main rect and on connections
class GNumberText(QtWidgets.QGraphicsTextItem):
    def __init__(self, parent, node):
        super().__init__(str(node.val), parent=parent)
        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.setTextWidth(100)
        self.setTabChangesFocus(True)
        self.node = node

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # Ignore enter key
        if event.key() == Qt.Key_Return:
            event.accept()

    def setColour(self, col):
        pass


@xformtype
class XFormNumber(XFormType):
    def __init__(self):
        super().__init__("number", "maths", "0.0.0")
        self.addOutputConnector("", "number")
        self.autoserialise = ('val',)
        self.hasEnable = True

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
        node.setOutput(0, node.val)

