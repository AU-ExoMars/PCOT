from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtWidgets import QGraphicsRectItem

from pcot import ui
from pcot.xform import xformtype, XFormType


class GStringText(QtWidgets.QGraphicsTextItem):
    def __init__(self, parent, node):
        super().__init__(node.string, parent=parent)
        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.setTextWidth(50)
        self.setTabChangesFocus(True)
        self.rect = parent
        self.node = node

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.setPlainText(self.node.string)
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # return means "go!"
        if event.key() == QtCore.Qt.Key.Key_Return:
            self.node.mark()
            self.node.string = self.toPlainText()
            self.clearFocus()
            # no need to perform here; there is no output
            # self.node.graph.performNodes(self.node)
            event.accept()
        else:
            super().keyPressEvent(event)

    def setColour(self, col):
        pass


@xformtype
class XFormComment(XFormType):
    """Comment box"""
    def __init__(self):
        super().__init__("comment", "maths", "0.0.0")
        self.autoserialise = ('string',)

    ## build the text element of the graph scene object for the node. By default, this
    # will just create static text, but can be overridden.
    @staticmethod
    def buildText(n):
        x, y = n.xy
        text = GStringText(n.rect, n)
        text.setPos(x + ui.graphscene.XTEXTOFFSET, y + ui.graphscene.YTEXTOFFSET + ui.graphscene.CONNECTORHEIGHT)
        return text

    def createTab(self, n, w):
        return None

    def init(self, node):
        node.string = "comment"

    def perform(self, node):
        pass
