from PySide2.QtGui import QPainter
from PySide2.QtWidgets import QMessageBox

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot import ui
from pcot.rois import ROIPainted, getRadiusFromSlider
from pcot.ui.roiedit import PaintedEditor
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedDict
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
        t = [(k, v) for k, v in ROIPainted.TAGGEDDICTDEFINITION if k != "type"]
        self.params = TaggedDictType(*t)

    def createTab(self, n, w):
        return TabPainted(n, w)

    def init(self, node):
        node.brushSize = 20  # scale of 0-99 i.e. a slider value. Converted to pixel radius in getRadiusFromSlider()
        node.previewRadius = None  # previewing needs the image, but that's awkward - so we stash this data in perform()
        node.drawMode = 0

        # initialise the ROI data, which will consist of a bounding box within the image and
        # a 2D boolean map of pixels within the image - True pixels are in the ROI.

        node.roi = ROIPainted()

    def serialise(self, node):
        node.params = TaggedDict(self.params)
        # serialise the ROI into a TaggedDict, and copy fields from that into the node.params we just made.
        rser = node.roi.to_tagged_dict()
        for k in node.params.keys():
            node.params[k] = rser[k]
        # the caller will use node.params.
        return None

    def nodeDataFromParams(self, node):
        node.roi.from_tagged_dict(node.params)

    def setProps(self, node, img):
        # set the properties of the ROI
        node.roi.setContainingImageDimensions(img.w, img.h)
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

        node.roi.drawEdge = drawEdge
        node.roi.drawBox = drawBox

        node.previewRadius = getRadiusFromSlider(node.brushSize, img.w, img.h)

    def getMyROIs(self, node):
        return [node.roi]


class TabPainted(pcot.ui.tabs.Tab):
    """Editor for painted items.
    """
    def __init__(self, node, w):
        super().__init__(w, node, 'tabpainted.ui')
        self.editor = PaintedEditor(self)
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook = self
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.thickness.valueChanged.connect(self.thicknessChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.drawbg.stateChanged.connect(self.drawbgChanged)
        self.w.clearButton.pressed.connect(self.clearPressed)
        self.w.captionTop.toggled.connect(self.topChanged)
        self.w.drawMode.currentIndexChanged.connect(self.drawModeChanged)
        self.w.brushSize.valueChanged.connect(self.brushSizeChanged)
        self.w.canvas.canvas.setMouseTracking(True)
        self.mouseDown = False
        self.dontSetText = False
        # sync tab with node
        self.nodeChanged()

    def drawbgChanged(self, val):
        self.mark()
        self.node.roi.drawbg = (val != 0)
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
        self.node.roi.labeltop = checked
        self.changed()

    def fontSizeChanged(self, i):
        self.mark()
        self.node.roi.fontsize = i
        self.changed()

    def clearPressed(self):
        if QMessageBox.question(self.window, "Clear region", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.mark()
            self.node.roi.clear()
            self.changed()

    def textChanged(self, t):
        self.mark()
        self.node.roi.label = t
        # this will cause perform, which will cause onNodeChanged, which will
        # set the text again. We set a flag to stop the text being reset.
        self.dontSetText = True
        self.changed()
        # just rebuild tabs
        ui.mainwindow.MainUI.rebuildAll(scene=False)
        self.dontSetText = False

    def thicknessChanged(self, i):
        self.mark()
        self.node.roi.thickness = i
        self.changed()

    def colourPressed(self):
        col = pcot.utils.colour.colDialog(self.node.colour)
        if col is not None:
            self.mark()
            self.node.roi.colour = col
            self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setNode(self.node)
        self.w.canvas.setROINode(self.node)
        self.w.canvas.display(self.node.getOutput(XFormROIType.OUT_IMG))

        if not self.dontSetText:
            self.w.caption.setText(self.node.roi.label)
        self.w.fontsize.setValue(self.node.roi.fontsize)
        self.w.thickness.setValue(self.node.roi.thickness)
        self.w.captionTop.setChecked(self.node.roi.labeltop)
        self.w.brushSize.setValue(self.node.brushSize)
        self.w.drawMode.setCurrentIndex(self.node.drawMode)
        self.w.drawbg.setChecked(self.node.roi.drawbg)

        r, g, b = [x * 255 for x in self.node.roi.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

    # extra drawing! Preview of brush
    def canvasPaintHook(self, p: QPainter):
        self.editor.canvasPaintHook(p)

    def canvasMouseMoveEvent(self, x, y, e):
        self.editor.canvasMouseMoveEvent(x, y, e)

    def canvasMousePressEvent(self, x, y, e):
        self.editor.canvasMousePressEvent(x, y, e)

    def canvasMouseReleaseEvent(self, x, y, e):
        self.editor.canvasMouseReleaseEvent(x, y, e)
