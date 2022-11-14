"""This module deals with the widget which displays the graphical scene which
represents a graph (graphscene).
"""
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QMenu


class GraphView(QtWidgets.QGraphicsView):
    """The graphical view widget for the graph"""

    def __init__(self, parent=None):
        self.window = None
        self._prevMousePos = None
        super().__init__(parent)

    def setWindow(self, win, macroWindow):
        """sets the window this view is in, and also colours the view
        if it is showing a macro."""
        self.window = win
        if macroWindow:
            self.setStyleSheet("background-color:rgb(255,255,220)")

    def wheelEvent(self, evt):
        """handle mouse wheel zooming"""
        # Remove possible Anchors
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
        # Get Scene Pos
        target_viewport_pos = self.mapToScene(evt.pos())
        # Translate Scene
        self.translate(target_viewport_pos.x(), target_viewport_pos.y())
        # ZOOM
        if evt.angleDelta().y() > 0:
            factor = 1.2
        else:
            factor = 0.8333
        self.scale(factor, factor)

        # Translate back
        self.translate(-target_viewport_pos.x(), -target_viewport_pos.y())

    def mousePressEvent(self, event):
        """handle right mouse button panning (when zoomed). This works by
        looking at the delta from right mouse button events and applying it
        to the scroll bar."""
        if event.button() == Qt.RightButton:
            self._prevMousePos = event.pos()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """handle the mouse move event, doing panning if RMB down."""
        if event.buttons() == Qt.RightButton:
            offset = self._prevMousePos - event.pos()
            self._prevMousePos = event.pos()

            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + offset.y())
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + offset.x())
        else:
            super().mouseMoveEvent(event)

    # events for handling reception of dragged palette buttons - this
    # interacts with the palette buttons in palette.py

    def dragMoveEvent(self, e):
        """handle a drag move event from the palette"""
        e.accept()

    def dragEnterEvent(self, e):
        """handle starting a drag"""
        if e.mimeData().hasFormat('data/palette'):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        """handle dropping a palette node"""
        bs = e.mimeData().data('data/palette')
        # open the data stream and read the name
        stream = QtCore.QDataStream(bs)
        name = stream.readQString()
        # now we need to make one of those and add it to the graph!
        self.scene().mark()
        x = self.scene().graph.create(name)
        # we have to fudge up a position for this; normally grandalf
        # creates these. No need to set width and height.
        pos = self.mapToScene(e.pos())
        x.xy = (pos.x(), pos.y())
        # and build the scene with the new objects
        self.scene().rebuild()

    def keyPressEvent(self, event):
        """handle key presses"""
        if event.key() == Qt.Key_Delete:
            scene = self.scene()
            scene.mark()
            for n in scene.selection:
                # remove the nodes
                scene.graph.remove(n)
            scene.selection = []
            scene.rebuild()
            event.accept()
        else:
            # pass the event into the standard handler,
            # where it will be passed into any items that need it
            super().keyPressEvent(event)

    def contextMenuEvent(self, ev: QtGui.QContextMenuEvent) -> None:
        super().contextMenuEvent(ev)   # run the super's menu, which will run any item's menu
        if not ev.isAccepted():        # if the event wasn't accepted, run our menu
            menu = QMenu()
            reset = menu.addAction("Reset view")
            a = menu.exec_(ev.globalPos())
            if a == reset:
                self.fitAll()

    def fitAll(self):
        """Reset the view to fit the entire scene"""
        self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)

