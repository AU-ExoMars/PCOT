from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import Qt

from pcot.datum import Datum
import pcot.ui as ui
from pcot.sources import nullSourceSet
from pcot.value import Value
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

    def focusInEvent(self, event:QtGui.QFocusEvent) -> None:
        self.scene().lockDeleteKeys = True
        super().focusInEvent(event)

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.scene().lockDeleteKeys = False
        self.setFromTextAndRunIfRequired()
        # If I leave this in, I get an "internal object already deleted" for this obj. and even
        # keeping an extra ref. in the node doesn't seem to help.
        # super().focusOutEvent(event)

    def contextMenuEvent(self, event: 'QGraphicsSceneContextMenuEvent') -> None:
        """In QT5, the context menu in QGraphicsTextItem causes a segfault - we disable
        it here. https://bugreports.qt.io/browse/QTBUG-89563
        This is probably a good idea anyway, as it lets the node's context menu run"""
        event.ignore()

    def setFromTextAndRunIfRequired(self):
        v = self.toPlainText()
        if v != self.node.val:
            self.node.val = float(v)
            # we also have to tell the graph to perform from here
            self.node.graph.performNodes(self.node)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # return means "go!"
        if event.key() == Qt.Key_Return:
            try:
                self.node.mark()
                self.clearFocus()
                self.setFromTextAndRunIfRequired()
            except ValueError:
                self.node.unmark()
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
        self.addOutputConnector("", Datum.NUMBER)
        self.autoserialise = ('val',)

    ## build the text element of the graph scene object for the node. By default, this
    # will just create static text, but can be overridden. I've made it store the value
    # in the node because otherwise the underlying C++ object gets freed.
    @staticmethod
    def buildText(n):
        x, y = n.xy
        n.text = GNumberText(n.rect, n)
        n.text.setPos(x + ui.graphscene.XTEXTOFFSET, y + ui.graphscene.YTEXTOFFSET + ui.graphscene.CONNECTORHEIGHT)
        return n.text

    def createTab(self, n, w):
        return None

    def init(self, node):
        node.val = 0

    def perform(self, node):
        node.setOutput(0, Datum(Datum.NUMBER, Value(node.val, 0.0), nullSourceSet))
