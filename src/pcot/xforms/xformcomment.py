from typing import Tuple

from PySide2 import QtGui, QtWidgets, QtCore
from PySide2.QtGui import QColor, QFont, QPen

from pcot import ui
from pcot.parameters.taggedaggregates import TaggedDictType, taggedColourType
from pcot.ui.tabs import Tab
from pcot.utils.colour import colDialog
from pcot.xform import xformtype, XFormType


class GStringText(QtWidgets.QGraphicsTextItem):
    def __init__(self, parent, node):
        super().__init__(node.params.string, parent=parent)
        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.setTextWidth(50)
        self.setTabChangesFocus(True)
        self.rect = parent
        self.node = node

        font = QFont()
        font.setFamily('Sans Serif')
        font.setPixelSize(node.params.fontSize)
        self.setFont(font)

    def contextMenuEvent(self, event: 'QGraphicsSceneContextMenuEvent') -> None:
        """In QT5, the context menu in QGraphicsTextItem causes a segfault - we disable
        it here. https://bugreports.qt.io/browse/QTBUG-89563
        This is probably a good idea anyway, as it lets the node's context menu run"""
        event.ignore()

    def editDone(self):
        self.node.mark()
        self.node.params.string = self.toPlainText()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.editDone()
        self.scene().lockDeleteKeys = False
        super().focusOutEvent(event)

    def focusInEvent(self, event:QtGui.QFocusEvent) -> None:
        self.scene().lockDeleteKeys = True
        super().focusInEvent(event)

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
        super().__init__("comment", "utility", "0.0.0")
        self.resizable = True
        self.showPerformedCount = False
        self.params = TaggedDictType(
            string=("comment text", str, "comment"),
            boxColour=("box colour", taggedColourType(1,1,1), None),
            textColour=("text colour", taggedColourType(0,0,0), None),
            fontSize=("font size", int, 12)
        )

    def init(self, node):
        pass

    def nodeDataFromParams(self, node):
        # in older files, colour will be 0-255. Detect and cope.
        if node.params.boxColour[0] > 1:
            node.params.boxColour.set(*[x/255 for x in node.params.boxColour])
        if node.params.textColour[0] > 1:
            node.params.textColour.set(*[x/255 for x in node.params.textColour])

    ## build the text element of the graph scene object for the node. By default, this
    # will just create static text, but can be overridden.
    def buildText(self, n):
        x, y = n.xy
        text = GStringText(n.rect, n)
        text.setPos(x + ui.graphscene.XTEXTOFFSET, y + ui.graphscene.YTEXTOFFSET + ui.graphscene.CONNECTORHEIGHT)

        return text

    def getDefaultRectColour(self, n):
        return [x*255 for x in n.params.boxColour]

    def getTextColour(self, n):
        return [x*255 for x in n.params.textColour]

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
    r1, g1, b1 = [x*255 for x in col.get()]

    t = 255 if r1 + g1 + b1 < (128 * 3) else 0
    s = f"background-color: rgb({r1},{g1},{b1}); color: rgb({t},{t},{t})"
    b.setStyleSheet(s)



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
        self.node.params.string = self.w.text.toPlainText()
        # editing done button will change what it looks like in the graph (other things might too)

    def editDoneClicked(self):
        self.changed()

    def boxColourClicked(self):
        self.node.params.boxColour.set(*colDialog(self.node.params.boxColour))
        self.changed()

    def textColourClicked(self):
        self.node.params.textColour.set(*colDialog(self.node.params.textColour))
        self.changed()

    def fontSizeChanged(self, s):
        self.node.params.fontSize = int(s)
        self.changed()

    def onNodeChanged(self):
        setButtonColour(self.w.boxColourButton, self.node.params.boxColour)
        setButtonColour(self.w.textColourButton, self.node.params.textColour)
        self.w.text.setPlainText(self.node.params.string)
        self.w.fontSizeCombo.setCurrentText(str(self.node.params.fontSize))
