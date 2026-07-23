"""Handles editing actions for regions of interest, as canvas hooks."""
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QColor, QPainter
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QDialogButtonBox, QSpinBox

from pcot.utils.flood import FloodFillParams


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

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
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

    def __init__(self, tab):
        """We assume that the tab contains .w.canvas and .node. The tab will have a getROI() method to get the ROI."""
        self.mouseDown = False
        self.tab = tab
        self.dlg = None

    def roi(self):
        return self.tab.getROI()

    def canvasMouseMoveEvent(self, x2, y2, e):
        pass

    def canvasMousePressEvent(self, x, y, e):
        pass

    def canvasMouseReleaseEvent(self, x, y, e):
        pass

    def canvasKeyPressEvent(self, e):
        """Return True if the key was handled (stops the canvas's own generic pan/zoom
        keys from also acting on it), False/None otherwise."""
        return False

    def canvasPaintHook(self, p: QPainter):
        pass

    def openDialog(self, w, h):
        """Opens a numerical dialog editor using a list of the ROI's data elements and ranges (see roiFields doc)
        The w,h parameters are the size of the image, which act as limits on some fields (see __init__ docs)"""
        fields = self.roiFields
        if fields is not None:
            self.dlg = ROIEditDialog(None, self.roi(), w, h, fields)
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
            bb = self.roi().bb()
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
            self.roi().set(x, y, w, h)
            self.tab.changed()
        self.tab.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.mouseDown = True
            self.tab.mark()
            self.roi().set(x, y, 5, 5)
            self.tab.changed()
            self.tab.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False


class CircleEditor(ROIEditor):
    """Click+drag creates a circle: the click sets the centre, dragging sets the radius.
    With shift held, click+drag sets the radius of an existing circle without moving its centre.
    With ctrl held, click+drag moves an existing circle without changing its radius."""

    roiFields = (
        ('x', 0, 'w'),
        ('y', 0, 'h'),
        ('r', 0, None),
    )

    def setRadius(self, x2, y2):
        """Resize the circle about its current centre so it passes through (x2,y2)."""
        c = self.roi().get()
        x, y, r = c if c is not None else (0, 0, 0)
        dx = x - x2
        dy = y - y2
        r = math.sqrt(dx * dx + dy * dy)
        if r < 1:
            r = 1
        # we don't do a mark here to avoid multiple marks - one is done on mousedown.
        self.roi().set(x, y, r)
        self.tab.changed()
        self.tab.w.canvas.update()

    def setCentre(self, x, y):
        """Move the circle's centre to (x,y), keeping its radius."""
        c = self.roi().get()
        _, _, r = c if c is not None else (0, 0, 10)
        # we don't do a mark here to avoid multiple marks - one is done on mousedown.
        self.roi().set(x, y, r)
        self.tab.changed()
        self.tab.w.canvas.update()

    def canvasMouseMoveEvent(self, x2, y2, e):
        if self.mouseDown:
            if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
                # ctrl-drag: move the whole circle, keeping its radius
                self.setCentre(x2, y2)
            else:
                # plain or shift drag: set the radius about the fixed centre
                self.setRadius(x2, y2)

    def canvasMousePressEvent(self, x, y, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.mouseDown = True
        roi = self.roi()
        self.tab.mark()
        if e.modifiers() & Qt.KeyboardModifier.ShiftModifier and roi.get() is not None:
            # shift: keep the centre, set the radius so the circle passes through the click;
            # dragging then continues to adjust the radius
            self.setRadius(x, y)
        elif e.modifiers() & Qt.KeyboardModifier.ControlModifier and roi.get() is not None:
            # ctrl: move the centre to the click, keeping the radius;
            # dragging then continues to move the circle
            self.setCentre(x, y)
        else:
            # plain click: start a new circle here with a default radius;
            # dragging will then set the radius
            roi.set(x, y, 10)
            self.tab.changed()
            self.tab.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False


class PolyEditor(ROIEditor):
    roiFields = None

    def canvasMouseMoveEvent(self, x, y, _):
        if self.mouseDown:
            if self.roi().moveSelPoint(x, y):
                self.tab.changed()

    def canvasMousePressEvent(self, x, y, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.mouseDown = True
            self.tab.mark()
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.roi().addPoint(x, y)
            else:
                self.roi().selPoint(x, y)
            self.tab.changed()
            self.tab.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False

    def canvasKeyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Delete:
            self.tab.mark()
            self.roi().delSelPoint()
            self.tab.changed()
            return True
        return False


class PaintedEditor(ROIEditor):
    roiFields = None

    def __init__(self, tab):
        super().__init__(tab)
        self.mousePos = None

    # extra drawing! Preview of brush
    def canvasPaintHook(self, p: QPainter):
        c = self.tab.w.canvas
        if self.mousePos is not None and self.tab.node.previewRadius is not None:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QColor(*[v * 255 for v in self.tab.node.roi.colour]))
            r = self.tab.node.previewRadius / (c.canvas.getScale())
            p.drawEllipse(self.mousePos, r, r)

    def doSet(self, x, y, e):
        n = self.tab.node
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # we need to use the image stored in the node, which should be a copy of the original,
            # as the reference image for the flood fill. We have to fetch it from the node output.
            from pcot.xform import XFormROIType
            img = n.getOutput(XFormROIType.OUT_IMG)
            if img is not None:
                self.roi().fill(img, x, y, FloodFillParams(threshold=0.03))  # flood fill
        elif e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.roi().setCircle(x, y, n.brushSize, True, relativeSize=True)  # delete
        else:
            self.roi().setCircle(x, y, n.brushSize, False, relativeSize=True)

    def canvasMouseMoveEvent(self, x, y, e):
        self.mousePos = e.position()
        if self.mouseDown:
            self.doSet(x, y, e)
            self.tab.changed()
        self.tab.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        # self.tab.mark()    We avoid marking here, because we'll mark when we lift the mouse button.
        if e.button() == Qt.MouseButton.LeftButton:
            self.mouseDown = True
            self.doSet(x, y, e)
            self.tab.changed()
            self.tab.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.tab.mark()
        self.mouseDown = False
