import copy
import random
from functools import partial

import matplotlib
from PySide2.QtCore import Qt
from PySide2.QtGui import QPainter, QColor, QKeyEvent
from PySide2.QtWidgets import QMessageBox, QSpinBox

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot import ui
from pcot.datum import Datum
from pcot.rois import ROICircle, ROIPainted, ROI
from pcot.ui.variantwidget import VariantWidget
from pcot.utils.flood import FloodFillParams
from pcot.xform import xformtype, XFormType

# modes for the tab
PAINT_MODE_CIRCLE = 0
PAINT_MODE_FILL = 1


@xformtype
class XFormMultiDot(XFormType):
    """
    Add multiple small circle ROIs. Most subsequent operations will only
    be performed on the union of all regions of interest.
    Also outputs an RGB image annotated with the ROIs on the 'ann' RGB input,
    or the input image converted to RGB if that input is not connected.
    Note that this type doesn't inherit from XFormROI.
    """

    # constants enumerating the outputs
    OUT_IMG = 0
    IN_IMG = 0

    def __init__(self):
        super().__init__("multidot", "regions", "0.0.0")
        self.addInputConnector("input", Datum.IMG)
        self.addOutputConnector("img", Datum.IMG, "image with ROIs")
        self.autoserialise = (
            ('dotSize', 10),
            ('fontsize', 10),
            ('thickness', 0),
            ('colour', (1, 1, 0)),
            ('tolerance', 3),
            ('drawbg', True)
        )

    def createTab(self, n, w):
        return TabMultiDot(n, w)

    def init(self, node):
        node.img = None
        node.fontsize = 10
        node.thickness = 0
        node.colour = (1, 1, 0)
        node.tolerance = 3
        node.paintMode = PAINT_MODE_CIRCLE   # not serialised
        node.drawbg = True
        node.prefix = ''  # the name we're going to set by default, it will be followed by an int
        node.dotSize = 10  # dot radius in pixels
        node.previewRadius = None  # previewing needs the image, but that's awkward - so we stash this data in perform()
        node.selected = None  # selected ROICircle
        node.rois = []  # this will be a list of ROICircle

    #    def uichange(self, n):
    #        n.timesPerformed += 1
    #        self.perform(n)

    @staticmethod
    def selectionHighlight(r, img):
        """Add some kind of highlighting to image for the the selected ROI. This is done by
        adding an annotation to the image, which is then drawn by the image viewer"""
        if r:
            if isinstance(r, ROICircle):
                # here we add a circle around the selected ROI as an annotation
                r = ROICircle(r.x, r.y, r.r * 1.3)
                r.setContainingImageDimensions(img.w, img.h)
            elif isinstance(r, ROIPainted):
                # not sure what to do here - reproduce the painted ROI, dilate it and add it as an annotation?
                # It will do for now
                r = r.dilated(5)
            if r is not None:
                r.colour = r.colour
                img.annotations = [r]

    def perform(self, node):
        img = node.getInput(self.IN_IMG, Datum.IMG)

        if img is None:
            # no image
            node.setOutput(self.OUT_IMG, None)
            node.img = None
        else:
            self.setProps(node, img)
            for r in node.rois:
                # copy parameters shared by all these ROIs into each one. Ugh, I know.
                r.drawBox = (r == node.selected)
                r.thickness = node.thickness
                r.fontsize = node.fontsize
                r.drawbg = node.drawbg
            # copy image and append ROIs to it
            img = img.copy()
            img.rois += node.rois

            if node.selected is not None:
                self.selectionHighlight(node.selected, img)

            # set mapping from node
            img.setMapping(node.mapping)
            node.img = img

        node.setOutput(self.OUT_IMG, Datum(Datum.IMG, node.img))  # output image and ROI

    def serialise(self, node):
        """We serialise the ROIs - this will store their type too"""
        return {'rois': [r.serialise() for r in node.rois]}

    def deserialise(self, node, d):
        # run through the ROIs, deserialising them
        for r in d['rois']:
            if 'type' not in r:
                # add the missing type field for old files
                r['type'] = 'circle'
        rs = [ROI.fromSerialised(x) for x in d['rois']]
        # filter out any zero-radius circles
        node.rois = [r for r in rs if isinstance(r, ROIPainted) or r.r > 0]

    def setProps(self, node, img):
        node.previewRadius = node.dotSize

    def getROIDesc(self, node):
        n = sum([0 if r is None else 1 for r in node.rois])
        s = sum([0 if r is None else r.pixels() for r in node.rois])
        return "{} pixels\nin {} ROIs".format(s, n)

    def getMyROIs(self, node):
        return node.rois


class ModeWidget(VariantWidget):
    """Widget for selecting the paint mode for painting ROIs"""
    def __init__(self, w):
        # the modes for this tab, must be in the same order as the MODE_ constants
        super().__init__("Paint mode", ['Circle', 'Fill'], w)


class TabMultiDot(pcot.ui.tabs.Tab):
    # modes for creating ROIs, determined by the order of the pages in the stack widget
    CIRCLE = 0
    PAINTED = 1

    def __init__(self, node, w):
        super().__init__(w, node, 'tabmultidot.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook = self
        self.w.canvas.keyHook = self
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.thickness.valueChanged.connect(self.thicknessChanged)
        self.w.drawbg.stateChanged.connect(self.drawbgChanged)
        self.w.caption.returnPressed.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.clearButton.pressed.connect(self.clearPressed)
        self.w.recolour.pressed.connect(self.recolourPressed)
        self.w.dotSize.editingFinished.connect(self.dotSizeChanged)
        self.w.tolerance.valueChanged.connect(self.toleranceChanged)
        self.w.paintMode.changed.connect(self.modeChanged)

        self.pageButtons = [
            self.w.radioCircles,
            self.w.radioPainted
        ]
        for x in self.pageButtons:
            # this avoids the lambda binding the wrong value of x
            # https://stackoverflow.com/questions/2295290/what-do-lambda-function-closures-capture
            # late binding: the value of x is looked up when the code in the closure is executed,
            # not when it is defined. So we need to bind it to a local variable.
            x.clicked.connect(partial(lambda xx: self.pageButtonClicked(xx), x))

        self.w.canvas.canvas.setMouseTracking(True)
        self.mousePos = None
        self.dragging = False
        self.dontSetText = False
        self.setPage(self.CIRCLE)
        # sync tab with node
        self.nodeChanged()

    def pageButtonClicked(self, x):
        i = self.pageButtons.index(x)
        self.setPage(i)

    def drawbgChanged(self, val):
        self.mark()
        self.node.drawbg = (val != 0)
        self.changed()

    def modeChanged(self, i):
        self.node.paintMode = i

    def dotSizeChanged(self):
        val = self.w.dotSize.value()
        self.node.dotSize = val
        if self.node.selected is not None:
            self.mark()
            self.node.selected.r = val
        self.changed()
        self.w.canvas.redisplay()

    def justMark(self):
        self.mark()

    def fontSizeChanged(self, i):
        self.mark()
        self.node.fontsize = i
        self.changed()

    def toleranceChanged(self, i):
        self.mark()
        self.node.tolerance = i
        self.changed()

    def recolourPressed(self):
        """recolour all dots randomly, and do it differently each time pressed"""
        self.mark()
        cols = matplotlib.cm.get_cmap('Dark2').colors
        base = random.randint(0, 1000)
        for idx, r in enumerate(self.node.rois):
            xx = idx + base
            r.colour = cols[xx % len(cols)]
        self.changed()

    def clearPressed(self):
        if QMessageBox.question(self.window, "Clear regions", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.mark()
            self.node.rois = []
            self.node.selected = None
            self.changed()

    def textChanged(self):
        t = self.w.caption.text()
        if self.node.selected is not None:
            self.node.selected.label = t  # except for this special case!
            self.changed()
        self.w.canvas.setFocus(Qt.OtherFocusReason)

    def thicknessChanged(self, i):
        self.mark()
        self.node.thickness = i
        self.changed()

    def colourPressed(self):
        col = pcot.utils.colour.colDialog(self.node.colour)
        if col is not None:
            self.mark()
            self.node.colour = col
            if self.node.selected is not None:
                self.node.selected.colour = col
            self.changed()

    def setPage(self, i):
        """Set the page to the given index"""
        self.w.stackedWidget.setCurrentIndex(i)
        for idx, x in enumerate(self.pageButtons):
            x.setChecked(idx == i)

    def getPage(self):
        """Get the index of the current page"""
        return self.w.stackedWidget.currentIndex()

    # call this when the selected state changes; changes the enabled state of contropls which
    # allow the selected node to be edited.
    def updateSelected(self):
        b = self.node.selected is not None
        self.w.caplabel.setEnabled(b)
        self.w.caption.setEnabled(b)
        if b:
            # we're selecting a node, so set the text and dot size
            if self.node.img:
                r = self.node.selected.r
                self.w.dotSize.setValue(r)
            self.w.caption.setText(self.node.selected.label)

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.canvas.setROINode(self.node)
        self.w.canvas.display(self.node.img)

        if self.node.selected:
            # If an ROI is selected, we copy the ROI's label and dot size to the controls

            # this is either the radius of the circle ROI, or the size of the last brush that was used
            # for a painted ROI
            ds = self.node.selected.r
            s = self.node.selected.label
        else:
            # otherwise we use the default values from the node
            ds = self.node.dotSize
            s = self.node.prefix

        if not self.dontSetText:
            self.w.caption.setText(s)

        self.w.dotSize.setValue(ds)

        self.w.fontsize.setValue(self.node.fontsize)
        self.w.thickness.setValue(self.node.thickness)
        self.w.drawbg.setChecked(self.node.drawbg)
        self.w.tolerance.setValue(self.node.tolerance)
        self.w.paintMode.set(self.node.paintMode)

        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

    def canvasPaintHook(self, p: QPainter):
        """Called after the canvas has painted the image, but before it has painted the ROIs. We use
        this to preview the circular brush we are using"""
        if self.mousePos is not None and self.node.previewRadius is not None:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(*[v * 255 for v in self.node.colour]))
            r = self.node.previewRadius / (self.w.canvas.canvas.getScale())
            p.drawEllipse(self.mousePos, r, r)

    def mouseDragCircleMode(self, x, y):
        """We are moving the mouse with the button down in circle mode. This changes the centre of the circle."""
        node = self.node
        if node.selected is not None:
            node.selected.x = x
            node.selected.y = y
            self.changed()

    def mouseDragPaintMode(self, x, y):
        """We are moving the mouse with the button down in paint mode. This paints a circle."""
        node = self.node
        if node.selected is not None:
            # todo - handle paint mode drag
            ui.log("Not implemented")

    def canvasMouseMoveEvent(self, x, y, e):
        """Mouse move handler. We use this differently depending on whether we are in circle or painted mode.
        In circle mode, we change the centre of the circle. In painted mode, we paint."""
        self.mousePos = e.pos()
        if self.dragging:
            if self.getPage() == self.CIRCLE:
                self.mouseDragCircleMode(x, y)
            else:
                self.mouseDragPaintMode(x, y)
        self.w.canvas.update()

    def getFreeLabel(self):
        """Return a free label for a new ROI"""
        idx = 0
        while True:
            # look for ROI with label "prefix idx"
            xx = [x for x in self.node.rois if x.label == self.node.prefix + str(idx)]
            if len(xx) == 0:
                # none found, return this label
                return self.node.prefix + str(idx)
            idx = idx + 1  # increment and keep looking

    def handleClickNoSelection(self, node, x, y, modifiers):
        """The button has been pressed, no ROI is selected"""

        if modifiers & Qt.ShiftModifier:
            # shift key is down, so create a new ROI and select it.
            idx = self.getFreeLabel()
            r = None
            # either circle or painted, depending on which "page"
            # the UI is showing.
            if self.getPage() == self.CIRCLE:
                r = ROICircle(x, y, self.node.dotSize)
            elif self.getPage() == self.PAINTED:
                r = ROIPainted(containingImageDimensions=
                               (self.node.img.w, self.node.img.h))
                # if the control key is also down, we do a flood fill. Otherwise
                # we do a circle.
                if modifiers & Qt.ControlModifier:
                    r.fill(node.img, x, y)
                else:
                    r.setCircle(x, y, self.node.dotSize)
            if r is not None:
                r.label = node.prefix + str(idx)
                r.colour = node.colour
                node.rois.append(r)
                node.selected = r
                self.changed()
        else:
            # shift key is not down, so we are just selecting an existing ROI
            node.selected = None  # deselect any existing selection
            r = self.findROI(x, y)
            if r is not None:
                node.selected = r
                # if we selected a circle, set the dragging flag
                if isinstance(r, ROICircle):
                    self.dragging = True
                self.changed()

    def handleClickWithSelection(self, node, x, y, modifiers):
        """We are clicking, but this time we have a selection. What happens
        depends on what is selected."""
        r = node.selected

        # if control and shift are down, and we have a painted selected,
        # we do a flood fill.
        if modifiers & Qt.ControlModifier and modifiers & Qt.ShiftModifier and isinstance(r, ROIPainted):
            r.fill(node.img, x, y)
            self.changed()
            return

        # if the shift key is down, we just add an ROI as if there was no
        # selection. The same applies when a circle is selected - we just
        # deselect it and add a new ROI by calling the other click handler.
        if isinstance(r, ROICircle) or (modifiers & Qt.ShiftModifier):
            # we have a circle selected - that doesn't mean anything, we just
            # deselect it and try to select something else calling the other
            # click handler.
            node.selected = None
            self.handleClickNoSelection(node, x, y, modifiers)
        elif isinstance(r, ROIPainted):
            # we have a painted ROI selected. What happens depends on the
            # modifier keys.

            # If the control key is down, we add a circle to the ROI
            if modifiers & Qt.ControlModifier:
                r.setCircle(x, y, node.dotSize, relativeSize=False)
                self.changed()
            # If the alt key is down, we remove a circle from the ROI
            elif modifiers & Qt.AltModifier:
                r.setCircle(x, y, node.dotSize, delete=True, relativeSize=False)
                # we may have deleted the last circle, in which case we delete the ROI
                if r.bb() is None:
                    node.rois.remove(r)
                    node.selected = None
                self.changed()
            # no modifier keys, so we just act as if there was no selection
            else:
                self.handleClickNoSelection(node, x, y, modifiers)

    def findROI(self, x, y):
        """Find an ROI at the given point, or return None"""
        for r in self.node.rois:
            if (x, y) in r:
                return r
        return None

    def addNewROI(self, r):
        """Add a new ROI to the list, select it, and give it a label"""
        node = self.node
        r.label = self.getFreeLabel()
        r.colour = node.colour
        node.rois.append(r)
        node.selected = r

    def fill(self, node, x, y):
        """Fill the selected ROI if it is a painted ROI"""
        params = FloodFillParams()
        params.threshold = node.tolerance
        node.selected.fill(node.img, x, y, fillparams=params)
        ui.log(f"filling at {x}, {y} with tolerance {node.tolerance}")

    def canvasMousePressEvent(self, x, y, e):
        """Mouse button has gone down"""
        node = self.node
        alt = e.modifiers() & Qt.AltModifier
        ctrl = e.modifiers() & Qt.ControlModifier
        shift = e.modifiers() & Qt.ShiftModifier

        if shift:
            # shift key is down, so we are going to create a new ROI. What kind of ROI depends on
            # which "page" we are on.
            self.mark()
            if self.getPage() == self.CIRCLE:
                # circle page, so create a circle
                r = ROICircle(x, y, node.dotSize)
                self.addNewROI(r)  # add and select the new ROI
            else:
                # painted page, so create a painted ROI using either a circle or a flood fill
                # depending on which paint mode is selected in the node.
                r = ROIPainted(containingImageDimensions=
                               (node.img.w, node.img.h))
                self.addNewROI(r)  # add and select the new ROI
                if node.paintMode == PAINT_MODE_CIRCLE:
                    r.setCircle(x, y, node.dotSize)
                else:
                    self.fill(node, x, y)
            self.changed()
        elif ctrl:
            # control key down - we add to the selected ROI, but it has to be the right kind of ROI
            # and we have to be on the painted page.
            if self.getPage() == self.PAINTED and isinstance(node.selected, ROIPainted):
                r = node.selected
                if node.paintMode == PAINT_MODE_CIRCLE:
                    r.setCircle(x, y, node.dotSize)
                else:
                    self.fill(node, x, y)
                self.changed()
        elif alt:
            # alt key down - we remove from the selected ROI, but it has to be the right kind of ROI
            # and we have to be on the painted page.
            if self.getPage() == self.PAINTED and isinstance(node.selected, ROIPainted):
                r = node.selected
                if node.paintMode == PAINT_MODE_CIRCLE:
                    r.setCircle(x, y, node.dotSize, delete=True)
                self.changed()
        else:
            # no modifier down. Select and ROI and if it is a circle, start dragging it.
            r = self.findROI(x, y)
            if r is not None:
                node.selected = r
                # if we selected a circle, set the dragging flag and go into the circle page
                if isinstance(r, ROICircle):
                    self.dragging = True
                    self.setPage(self.CIRCLE)
                else:
                    self.setPage(self.PAINTED)  # otherwise go into the painted page

        self.updateSelected()  # doesn't matter if this gets called even when we haven't changed selection
        self.w.canvas.update()

    def canvasKeyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k == Qt.Key_Delete:
            # delete key - delete the selected ROI
            n = self.node
            if n.selected is not None and n.selected in n.rois:
                self.mark()
                n.rois.remove(n.selected)
                n.selected = None
                self.dragging = False  # just in case
                self.updateSelected()
                self.changed()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.dragging = False
        self.changed()
