from typing import Tuple

from PySide2 import QtGui, QtWidgets, QtCore
from PySide2.QtGui import QColor, QFont, QPen

from pcot import ui
from pcot.ui.tabs import Tab
from pcot.xform import xformtype, XFormType


class GStringText(QtWidgets.QGraphicsTextItem):
    def __init__(self, parent, node):
        super().__init__(node.string, parent=parent)
        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.setTextWidth(50)
        self.setTabChangesFocus(True)
        self.rect = parent
        self.node = node

        font = QFont()
        font.setFamily('Sans Serif')
        font.setPixelSize(node.fontSize)
        self.setFont(font)

    def contextMenuEvent(self, event: 'QGraphicsSceneContextMenuEvent') -> None:
        """In QT5, the context menu in QGraphicsTextItem causes a segfault - we disable
        it here. https://bugreports.qt.io/browse/QTBUG-89563
        This is probably a good idea anyway, as it lets the node's context menu run"""
        event.ignore()

    def editDone(self):
        self.node.mark()
        self.node.string = self.toPlainText()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.editDone()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # return means "go!"
        if event.key() == QtCore.Qt.Key.Key_Return:
            self.clearFocus()
            # no need to perform here; there is no output
            # self.node.graph.performNodes(self.node)
            event.accept()
        else:
            super().keyPressEvent(event)

    def setColour(self, col):
        self.setDefaultTextColor(col)


@xformtype
class XFormComment(XFormType):
    """Comment box"""

    def __init__(self):
        super().__init__("comment", "maths", "0.0.0")
        self.resizable = True
        self.showPerformedCount = False
        self.autoserialise = ('string', 'boxColour', 'textColour', 'fontSize')

    def init(self, node):
        node.string = "comment"
        node.boxColour = (255, 255, 255)
        node.textColour = (0, 0, 0)
        node.fontSize = 12

    ## build the text element of the graph scene object for the node. By default, this
    # will just create static text, but can be overridden.
    @staticmethod
    def buildText(n):
        x, y = n.xy
        text = GStringText(n.rect, n)
        text.setPos(x + ui.graphscene.XTEXTOFFSET, y + ui.graphscene.YTEXTOFFSET + ui.graphscene.CONNECTORHEIGHT)

        return text

    def getDefaultRectColour(self, n):
        return n.boxColour

    def getTextColour(self, n):
        return n.textColour

    def resizeDone(self, n):
        t = n.rect.text
        t.setTextWidth(n.w - 10)

    def setRectParams(self, r):
        r.setPen(QPen(QColor(200, 200, 200)))

    def createTab(self, n, w):
        return TabComment(n, w)

    def perform(self, node):
        pass


def setButtonColour(b, col):
    b.setAutoFillBackground(True)
    r1, g1, b1 = col
    t = 255 if r1 + g1 + b1 < (128 * 3) else 0
    s = f"background-color: rgb({r1},{g1},{b1}); color: rgb({t},{t},{t})"
    b.setStyleSheet(s)


def colourDialog(col: Tuple[int, int, int]):
    r, g, b = col
    col = QColor(r, g, b)
    col = QtWidgets.QColorDialog.getColor(col, None)
    if col.isValid():
        return col.red(), col.green(), col.blue()
    else:
        return r, g, b


class TabComment(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabcomment.ui')
        self.w.boxColourButton.clicked.connect(self.boxColourClicked)
        self.w.textColourButton.clicked.connect(self.textColourClicked)
        self.w.fontSizeCombo.currentTextChanged.connect(self.fontSizeChanged)
        self.w.editDone.clicked.connect(self.editDoneClicked)
        self.w.text.textChanged.connect(self.textChanged)
        self.nodeChanged()

    def textChanged(self):
        self.node.string = self.w.text.toPlainText()
        # editing done button will change what it looks like in the graph (other things might too)

    def editDoneClicked(self):
        self.changed()

    def boxColourClicked(self):
        self.node.boxColour = colourDialog(self.node.boxColour)
        self.changed()

    def textColourClicked(self):
        self.node.textColour = colourDialog(self.node.textColour)
        self.changed()

    def fontSizeChanged(self, s):
        self.node.fontSize = int(s)
        self.changed()

    def onNodeChanged(self):
        setButtonColour(self.w.boxColourButton, self.node.boxColour)
        setButtonColour(self.w.textColourButton, self.node.textColour)
        self.w.text.setPlainText(self.node.string)
        self.w.fontSizeCombo.setCurrentText(str(self.node.fontSize))
