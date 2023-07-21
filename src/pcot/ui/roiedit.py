"""Handles editing actions for regions of interest, as canvas hooks."""
import math

from PySide2.QtCore import Qt
from PySide2.QtGui import QKeyEvent, QColor, QPainter


class ROIEditor:
    def __init__(self, tab, roi):
        """We assume that the tab contains .w.canvas and .node."""
        self.mouseDown = False
        self.tab = tab
        self.roi = roi

    def canvasMouseMoveEvent(self, x2, y2, e):
        pass

    def canvasMousePressEvent(self, x, y, e):
        pass

    def canvasMouseReleaseEvent(self, x, y, e):
        pass

    def canvasKeyPressEvent(self, e):
        pass

    def canvasPaintHook(self, p: QPainter):
        pass


class RectEditor(ROIEditor):
    def canvasMouseMoveEvent(self, x2, y2, e):
        if self.mouseDown:
            bb = self.roi.bb()
            if bb is None:
                x, y, w, h = 0, 0, 0, 0
            else:
                x, y, w, h = bb
            w = x2 - x
            h = y2 - y
            if w < 10:
                w = 10
            if h < 10:
                h = 10
            # we don't do a mark here to avoid multiple marks - one is done on mousedown.
            self.roi.set(x, y, w, h)
            self.tab.changed()
        self.tab.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        self.tab.mark()
        self.roi.set(x, y, 5, 5)
        self.tab.changed()
        self.tab.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False


class CircleEditor(ROIEditor):
    def setRadius(self, x2, y2):
        c = self.roi.get()
        x, y, r = c if c is not None else (0, 0, 0)
        dx = x - x2
        dy = y - y2
        r = math.sqrt(dx * dx + dy * dy)
        if r < 1:
            r = 1
        # we don't do a mark here to avoid multiple marks - one is done on mousedown.
        self.roi.set(x, y, r)
        self.tab.changed()
        self.tab.w.canvas.update()

    def canvasMouseMoveEvent(self, x2, y2, e):
        if self.mouseDown:
            self.setRadius(x2, y2)

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        self.tab.mark()
        if e.button() == Qt.RightButton and self.roi.get() is not None:
            self.setRadius(x, y)
        else:
            if e.modifiers() & Qt.ShiftModifier and self.roi.get() is not None:
                _, _, r = self.roi.get()
            else:
                r = 10
            self.roi.set(x, y, r)
            self.tab.changed()
            self.tab.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False


class PolyEditor(ROIEditor):
    def canvasMouseMoveEvent(self, x, y, _):
        if self.mouseDown:
            if self.roi.moveSelPoint(x, y):
                self.tab.changed()

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        self.tab.mark()
        if e.modifiers() & Qt.ShiftModifier:
            self.roi.addPoint(x, y)
        else:
            self.roi.selPoint(x, y)
        self.tab.changed()
        self.tab.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False

    def canvasKeyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key_Delete:
            self.tab.mark()
            self.roi.delSelPoint()
            self.tab.changed()


class PaintedEditor(ROIEditor):
    def __init__(self, tab, roi):
        super().__init__(tab, roi)
        self.node = tab.node
        self.mousePos = None

    # extra drawing! Preview of brush
    def canvasPaintHook(self, p: QPainter):
        c = self.tab.w.canvas
        if self.mousePos is not None and self.node.previewRadius is not None:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(*[v * 255 for v in self.node.colour]))
            r = self.node.previewRadius / (c.canvas.getScale())
            p.drawEllipse(self.mousePos, r, r)

    def doSet(self, x, y, e):
        if e.modifiers() & Qt.ShiftModifier:
            self.roi.setCircle(x, y, self.node.brushSize, True)  # delete
        else:
            self.roi.setCircle(x, y, self.node.brushSize, False)

    def canvasMouseMoveEvent(self, x, y, e):
        self.mousePos = e.pos()
        if self.mouseDown:
            self.doSet(x, y, e)
            self.tab.changed()
        self.tab.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        self.tab.mark()
        self.mouseDown = True
        self.doSet(x, y, e)
        self.tab.changed()
        self.tab.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.tab.mark()
        self.mouseDown = False


