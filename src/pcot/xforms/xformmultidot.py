import random
from functools import partial

import matplotlib
from PySide2.QtCore import Qt
from PySide2.QtGui import QPainter, QColor, QKeyEvent
from PySide2.QtWidgets import QMessageBox, QSpinBox

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot.datum import Datum
from pcot.rois import ROICircle
from pcot.xform import xformtype, XFormType


@xformtype
class XFormMultiDot(XFormType):
    """
    Add multiple small circle ROIs. Most subsequent operations will only
    be performed on the union of all regions of interest.
    Also outputs an RGB image annotated with the ROIs on the 'ann' RGB input,
    or the input image converted to RGB if that input is not connected.
    Note that this type doesn't inherit from XFormROI
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
            ('drawbg', True)
        )

    def createTab(self, n, w):
        return TabMultiDot(n, w)

    def init(self, node):
        node.img = None
        node.fontsize = 10
        node.thickness = 0
        node.colour = (1, 1, 0)
        node.drawbg = True
        node.prefix = ''  # the name we're going to set by default, it will be followed by an int
        node.dotSize = 10  # dot radius in pixels
        node.previewRadius = None  # previewing needs the image, but that's awkward - so we stash this data in perform()
        node.selected = None  # selected ROICircle
        node.rois = []  # this will be a list of ROICircle

#    def uichange(self, n):
#        n.timesPerformed += 1
#        self.perform(n)

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
            # we now add any selection as an extra annotation
            if node.selected:
                r = ROICircle(node.selected.x, node.selected.y, node.selected.r*1.3)
                r.setContainingImageDimensions(img.w, img.h)
                r.colour = node.selected.colour
                img.annotations = [r]
            # set mapping from node
            img.setMapping(node.mapping)
            node.img = img

        node.setOutput(self.OUT_IMG, Datum(Datum.IMG, node.img))  # output image and ROI

    def serialise(self, node):
        return {
            'rois': [n.serialise() for n in node.rois]
        }

    def deserialise(self, node, d):
        node.rois = []
        if 'rois' in d:
            for r in d['rois']:
                if r is not None:
                    roi = ROICircle()
                    roi.deserialise(r)
                    node.rois.append(roi)
        node.rois = [r for r in node.rois if r.r > 0]

    def setProps(self, node, img):
        node.previewRadius = node.dotSize

    def getROIDesc(self, node):
        n = sum([0 if r is None else 1 for r in node.rois])
        s = sum([0 if r is None else r.pixels() for r in node.rois])
        return "{} pixels\nin {} ROIs".format(s, n)

    def getMyROIs(self, node):
        return node.rois


class TabMultiDot(pcot.ui.tabs.Tab):
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
        self.setPage(0)
        # sync tab with node
        self.nodeChanged()

    def pageButtonClicked(self, x):
        i = self.pageButtons.index(x)
        self.setPage(i)

    def drawbgChanged(self, val):
        self.mark()
        self.node.drawbg = (val != 0)
        self.changed()

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

    def recolourPressed(self):
        """recolour all dots randomly, and do it differently each time pressed"""
        self.mark()
        cols = matplotlib.cm.get_cmap('Dark2').colors
        base = random.randint(0, 1000)
        for idx, r in enumerate(self.node.rois):
            xx = idx+base
            r.colour = cols[xx % len(cols)]
        self.changed()

    def clearPressed(self):
        if QMessageBox.question(self.window, "Clear regions", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.mark()
            self.node.rois = []
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
        for idx,x in enumerate(self.pageButtons):
            x.setChecked(idx == i)

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
            ds = self.node.selected.r
            s = self.node.selected.label
        else:
            ds = self.node.dotSize
            s = self.node.prefix

        if not self.dontSetText:
            self.w.caption.setText(s)

        self.w.dotSize.setValue(ds)

        self.w.fontsize.setValue(self.node.fontsize)
        self.w.thickness.setValue(self.node.thickness)
        self.w.drawbg.setChecked(self.node.drawbg)

        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

    # extra drawing! Preview of brush
    def canvasPaintHook(self, p: QPainter):
        c = self.w.canvas
        if self.mousePos is not None and self.node.previewRadius is not None:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(*[v * 255 for v in self.node.colour]))
            r = self.node.previewRadius / (self.w.canvas.canvas.getScale())
            p.drawEllipse(self.mousePos, r, r)

    def canvasMouseMoveEvent(self, x, y, e):
        self.mousePos = e.pos()
        node = self.node
        if self.dragging and node.selected is not None:
            node.selected.x = x
            node.selected.y = y
            self.changed()

        self.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        self.mark()
        node = self.node
        if e.modifiers() & Qt.ShiftModifier:
            idx = 0
            while True:
                # look for ROI with label "prefix idx"
                xx = [x for x in node.rois if x.label == node.prefix + str(idx)]
                if len(xx) == 0:  # none found, exit loop
                    break
                idx = idx + 1  # increment and keep looking
            # create ROI at correct radius, label etc. and add to list.
            r = ROICircle(x, y, self.node.dotSize)
            r.label = node.prefix + str(idx)
            r.colour = node.colour
            node.rois.append(r)
        else:
            mindist = None
            node.selected = None  # have to do this, otherwise we can never unselect
            self.dragging = True
            for r in node.rois:
                d = (x - r.x) ** 2 + (y - r.y) ** 2
                if d < 100 and (mindist is None or d < mindist):
                    node.selected = r
                    mindist = d

        self.updateSelected()
        self.changed()
        self.w.canvas.update()

    def canvasKeyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k == Qt.Key_Delete:
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
