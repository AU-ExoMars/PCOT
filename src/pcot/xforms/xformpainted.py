from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QMessageBox

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot import ui
from pcot.rois import ROIPainted, getRadiusFromSlider
from pcot.xform import xformtype, XFormROIType


@xformtype
class XFormPainted(XFormROIType):
    """
    Add a painted ROI to an image. Most subsequent operations will only
    be performed on the union of all regions of interest.
    Also outputs an RGB image annotated with the ROI on the 'ann' RGB input,
    or the input image converted to RGB if that input is not connected.
    """

    def __init__(self):
        super().__init__("painted", "regions", "0.0.0")
        self.autoserialise += ('brushSize', 'drawMode')

    def createTab(self, n, w):
        return TabPainted(n, w)

    def init(self, node):
        node.img = None
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.drawbg = True
        node.fontline = 2
        node.colour = (1, 1, 0)
        node.brushSize = 20  # scale of 0-99 i.e. a slider value. Converted to pixel radius in getRadiusFromSlider()
        node.previewRadius = None  # previewing needs the image, but that's awkward - so we stash this data in perform()
        node.drawMode = 0

        # initialise the ROI data, which will consist of a bounding box within the image and
        # a 2D boolean map of pixels within the image - True pixels are in the ROI.

        node.roi = ROIPainted()

    def serialise(self, node):
        return node.roi.serialise()

    def deserialise(self, node, d):
        node.roi.deserialise(d)

    def setProps(self, node, img):
        # set the properties of the ROI
        node.roi.setImageSize(img.w, img.h)
        if node.drawMode == 0:
            drawEdge = True
            drawBox = True
        elif node.drawMode == 1:
            drawEdge = True
            drawBox = False
        elif node.drawMode == 2:
            drawEdge = False
            drawBox = True
        else:
            drawEdge = False
            drawBox = False

        node.roi.setDrawProps(node.captiontop, node.colour, node.fontsize, node.fontline, node.drawbg)
        node.roi.drawEdge = drawEdge
        node.roi.drawBox = drawBox

        node.previewRadius = getRadiusFromSlider(node.brushSize, img.w, img.h)


class TabPainted(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabpainted.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook = self
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.drawbg.stateChanged.connect(self.drawbgChanged)
        self.w.clearButton.pressed.connect(self.clearPressed)
        self.w.captionTop.toggled.connect(self.topChanged)
        self.w.drawMode.currentIndexChanged.connect(self.drawModeChanged)
        self.w.brushSize.valueChanged.connect(self.brushSizeChanged)
        self.w.canvas.canvas.setMouseTracking(True)
        self.mousePos = None
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

    def brushSizeChanged(self, val):
        self.mark()
        self.node.brushSize = val
        self.changed()

    def topChanged(self, checked):
        self.mark()
        self.node.captiontop = checked
        self.changed()

    def fontSizeChanged(self, i):
        self.mark()
        self.node.fontsize = i
        self.changed()

    def clearPressed(self):
        if QMessageBox.question(self.parent(), "Clear region", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.mark()
            self.node.roi.clear()
            self.changed()

    def textChanged(self, t):
        self.mark()
        self.node.caption = t
        # this will cause perform, which will cause onNodeChanged, which will
        # set the text again. We set a flag to stop the text being reset.
        self.dontSetText = True
        self.changed()
        # just rebuild tabs
        ui.mainwindow.MainUI.rebuildAll(scene=False)
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

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.canvas.setROINode(self.node)
        if self.node.img is not None:
            # We're displaying a "premapped" image : this node's perform code is
            # responsible for doing the RGB mapping, unlike most other nodes where it's
            # done in the canvas for display purposes only. This is so that we can
            # actually output the RGB.
            # To render this, we call display in its three-argument form:
            # mapped RGB image, source image, node.
            # We need to node so we can force it to perform (and regenerate the mapped image)
            # when the mappings change.
            self.w.canvas.display(self.node.rgbImage, self.node.img, self.node)
        if not self.dontSetText:
            self.w.caption.setText(self.node.caption)
        self.w.fontsize.setValue(self.node.fontsize)
        self.w.fontline.setValue(self.node.fontline)
        self.w.captionTop.setChecked(self.node.captiontop)
        self.w.brushSize.setValue(self.node.brushSize)
        self.w.drawMode.setCurrentIndex(self.node.drawMode)
        self.w.drawbg.setChecked(self.node.drawbg)

        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

    # extra drawing! Preview of brush
    def canvasPaintHook(self, p: QPainter):
        c = self.w.canvas
        if self.mousePos is not None and self.node.previewRadius is not None:
            p.setPen(QColor(*[v * 255 for v in self.node.colour]))
            r = self.node.previewRadius / (self.w.canvas.canvas.getScale())
            p.drawEllipse(self.mousePos, r, r)

    def doSet(self, x, y, e):
        if e.modifiers() & Qt.ShiftModifier:
            self.node.roi.setCircle(x, y, self.node.brushSize, True)  # delete
        else:
            self.node.roi.setCircle(x, y, self.node.brushSize, False)

    def canvasMouseMoveEvent(self, x, y, e):
        self.mousePos = e.pos()
        if self.mouseDown:
            self.doSet(x, y, e)
            self.changed()
        self.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        self.mark()
        self.mouseDown = True
        self.doSet(x, y, e)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
