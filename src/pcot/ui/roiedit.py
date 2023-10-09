"""Handles editing actions for regions of interest, as canvas hooks."""
import math

from PySide2.QtCore import Qt
from PySide2.QtGui import QKeyEvent, QColor, QPainter
from PySide2.QtWidgets import QDialog, QGridLayout, QLabel, QDialogButtonBox, QSpinBox


class ROIEditDialog(QDialog):
    def __init__(self, parent, roi, w, h, roiFields):
        """Construct an ROI editor dialog using reflection.
        ROI is the ROI we are editing.
        w,h are the dimensions of the image containing the ROI - they are used as default values
        when a roi field's max is 'w' or 'h'. If the roi field max is None, the larger of the two is used.
        The roiFields are the names of attributes inside the ROI object, which are set from a class variable
        called by that name.
        """
        super().__init__(parent)
        layout = QGridLayout()
        row = 0
        self.spins = {}
        self.roi = roi
        for name, mn, mx in roiFields:
            label = QLabel(name)
            spin = QSpinBox()
            if mx is None:
                mx = w if w > h else h
            elif mx == 'w':
                mx = w
            elif mx == 'h':
                mx = h
            spin.setRange(mn, mx)
            spin.setValue(getattr(roi, name))
            layout.addWidget(label, row, 0)
            layout.addWidget(spin, row, 1)
            self.spins[name] = spin
            row += 1

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(lambda: self.finished(True))
        self.buttonBox.rejected.connect(lambda: self.finished(False))
        layout.addWidget(self.buttonBox, row, 0, 1, 2)

        self.setLayout(layout)

    def finished(self, accepted):
        if accepted:
            for name, spin in self.spins.items():
                setattr(self.roi, name, spin.value())
                self.roi.changed()
        self.close()


class ROIEditor:

    # these are fields we can edit in a dialog: they consist of triplets,
    #   - field name in the ROI object
    #   - min value (typically zero)
    #   - max value (if 'w' it's the width of the containing image, 'h' for the height, None for the max of both)

    roiFields = None

    def __init__(self, tab, roi):
        """We assume that the tab contains .w.canvas and .node."""
        self.mouseDown = False
        self.tab = tab
        self.roi = roi
        self.dlg = None

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

    def openDialog(self, w, h):
        """Opens a numerical dialog editor using a list of the ROI's data elements and ranges (see roiFields doc)
        The w,h parameters are the size of the image, which act as limits on some fields (see __init__ docs)"""
        fields = self.roiFields
        if fields is not None:
            self.dlg = ROIEditDialog(None, self.roi, w, h, fields)
            self.dlg.open()


class RectEditor(ROIEditor):
    roiFields = (
        ('x', 0, 'w'),
        ('y', 0, 'h'),
        ('w', 0, None),
        ('h', 0, None),
    )

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
    roiFields = (
        ('x', 0, 'w'),
        ('y', 0, 'h'),
        ('r', 0, None),
    )

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

    roiFields = None

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

    roiFields = None

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
