from PySide2.QtCore import Qt
from PySide2.QtGui import QKeyEvent
from PySide2.QtWidgets import QMessageBox

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text

from pcot.rois import ROIPoly
from pcot.xform import xformtype, XFormROIType


@xformtype
class XformPoly(XFormROIType):
    """
    Add a polygonal ROI to an image.
    Most subsequent operations will only
    be performed on the union of all regions of interest.
    Also outputs an RGB image annotated with the ROI on the 'ann' RGB input, or the input
    image converted to RGB if that input is not connected.
    """

    def __init__(self):
        super().__init__("poly", "regions", "0.0.0")
        self.autoserialise += ('drawMode',)

    def createTab(self, n, w):
        return TabPoly(n, w)

    def init(self, node):
        node.img = None
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.fontline = 2
        node.drawbg = True
        node.colour = (1, 1, 0)
        node.drawMode = 0

        # initialise the ROI data, which will consist of a bounding box within the image and
        # a 2D boolean map of pixels within the image - True pixels are in the ROI.

        node.roi = ROIPoly()

    def serialise(self, node):
        return node.roi.serialise()

    def deserialise(self, node, d):
        node.roi.deserialise(d)

    def setProps(self, node, img):
        node.roi.setImageSize(img.w, img.h)
        if node.drawMode == 0:
            drawPoints = True
            drawBox = True
        elif node.drawMode == 1:
            drawPoints = True
            drawBox = False
        else:
            drawPoints = False
            drawBox = False

        node.roi.setDrawProps(node.captiontop, node.colour, node.fontsize, node.fontline, node.drawbg)
        node.roi.drawPoints = drawPoints
        node.roi.drawBox = drawBox

    def getMyROIs(self, node):
        return [node.roi]



class TabPoly(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabpoly.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.mouseHook = self
        self.w.canvas.keyHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.drawbg.stateChanged.connect(self.drawbgChanged)
        self.w.clearButton.pressed.connect(self.clearPressed)
        self.w.captionTop.toggled.connect(self.topChanged)
        self.w.drawMode.currentIndexChanged.connect(self.drawModeChanged)

        self.mouseDown = False
        self.dontSetText = False
        # sync tab with node
        self.nodeChanged()

    def drawbgChanged(self, val):
        self.mark()
        self.node.drawbg = (val != 0)
        self.changed()

    def drawModeChanged(self, idx):
        self.mark()
        self.node.drawMode = idx
        self.changed()

    def topChanged(self, checked):
        self.mark()
        self.node.captiontop = checked
        self.changed()

    def fontSizeChanged(self, i):
        self.mark()
        self.node.fontsize = i
        self.changed()

    def textChanged(self, t):
        self.mark()
        self.node.caption = t
        # this will cause perform, which will cause onNodeChanged, which will
        # set the text again. We set a flag to stop the text being reset.
        self.dontSetText = True
        self.changed()
        self.dontSetText = False

    def fontLineChanged(self, i):
        self.mark()
        self.node.fontline = i
        self.changed()

    def colourPressed(self):
        col = pcot.utils.colour.colDialog(self.node.colour)
        if col is not None:
            self.mark()
            self.node.colour = col
            self.changed()

    def clearPressed(self):
        if QMessageBox.question(self.window, "Clear region", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.mark()
            self.node.roi.clear()
            self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.canvas.setROINode(self.node)
        self.w.canvas.display(self.node.img)
        if not self.dontSetText:
            self.w.caption.setText(self.node.caption)
        self.w.drawbg.setChecked(self.node.drawbg)
        self.w.fontsize.setValue(self.node.fontsize)
        self.w.fontline.setValue(self.node.fontline)
        self.w.captionTop.setChecked(self.node.captiontop)
        self.w.drawMode.setCurrentIndex(self.node.drawMode)
        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

    def canvasMouseMoveEvent(self, x, y, e):
        if self.mouseDown:
            if self.node.roi.moveSelPoint(x, y):
                self.changed()

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        self.mark()
        if e.modifiers() & Qt.ShiftModifier:
            self.node.roi.addPoint(x, y)
        else:
            self.node.roi.selPoint(x, y)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False

    def canvasKeyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key_Delete:
            self.mark()
            self.node.roi.delSelPoint()
            self.changed()
