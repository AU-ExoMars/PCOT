"""This module deals with the widget which displays the graphical scene which
represents a graph (graphscene).
"""
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu
import logging

from pcot.ui import theme

logger = logging.getLogger(__name__)

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
            self.setStyleSheet(theme.macroWindowStyle())

    # limits on the view scale, so the graph can't be zoomed into invisibility
    MINSCALE = 0.05
    MAXSCALE = 10.0

    def zoomAt(self, pos, factor):
        """zoom by a factor, keeping the scene point under the viewport position (a QPoint) fixed"""
        # clamp the factor so the resulting scale stays within limits
        cur = self.transform().m11()
        factor = max(self.MINSCALE / cur, min(self.MAXSCALE / cur, factor))
        # Remove possible Anchors
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor)
        # Get Scene Pos
        target_viewport_pos = self.mapToScene(pos)
        # Translate Scene
        self.translate(target_viewport_pos.x(), target_viewport_pos.y())
        # ZOOM
        self.scale(factor, factor)
        # Translate back
        self.translate(-target_viewport_pos.x(), -target_viewport_pos.y())

    def wheelEvent(self, evt):
        """handle mouse wheel zooming"""
        # Trackpads (notably on macOS) send a stream of many small deltas, some of which have no
        # vertical component at all, so the zoom has to be proportional to the delta rather than
        # a fixed step per event. One standard mouse wheel notch is 120, giving a factor of 1.2.
        dy = evt.angleDelta().y()
        if dy == 0:
            evt.accept()
            return
        self.zoomAt(evt.position().toPoint(), 1.2 ** (dy / 120.0))
        evt.accept()

    def viewportEvent(self, evt):
        """handle trackpad pinch-to-zoom (only generated on macOS)"""
        if evt.type() == QtCore.QEvent.Type.NativeGesture and \
                evt.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
            self.zoomAt(evt.position().toPoint(), 1.0 + evt.value())
            return True
        return super().viewportEvent(evt)

    def mousePressEvent(self, event):
        """handle right mouse button panning (when zoomed). This works by
        looking at the delta from right mouse button events and applying it
        to the scroll bar."""
        if event.button() == Qt.MouseButton.RightButton:
            self._prevMousePos = event.pos()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """handle the mouse move event, doing panning if RMB down."""
        if event.buttons() == Qt.MouseButton.RightButton:
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

        if name in self.window.doc.macros and self.window.isMacro():
            from pcot.ui import error
            error("Macro in macro not permitted")
            return


        # now we need to make one of those and add it to the graph!
        node = self.window.palette.createNodeByName(name)
        # we have to fudge up a position for this, it will have been given a default position.
        pos = self.mapToScene(e.pos())
        # we use the default width and height because the actual width and height haven't yet been calculated
        w = node.type.defaultWidth
        h = node.type.defaultHeight
        logger.debug(f"Drop event at {pos.x()},{pos.y()}, node size {w},{h}")
        node.xy = (pos.x() - w/2, pos.y() - h/2)
        # and build the scene with the new objects
        self.scene().rebuild()

    def keyPressEvent(self, event):
        """handle key presses"""
        scene = self.scene()#
        # we ignore these keys sometimes, typically when text item inside a box is being edited.
        if not scene.lockDeleteKeys and (event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace):
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
            a = menu.exec(ev.globalPos())
            if a == reset:
                self.fitAll()

    def fitAll(self):
        """Reset the view to fit the entire scene"""
        self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def repaint(self, *args, **kwargs):
        logger.debug("Repaint forced")
        super().repaint(*args,**kwargs)