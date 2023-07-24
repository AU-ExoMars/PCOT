import math

from PySide2.QtCore import Qt
from PySide2.QtGui import QIntValidator, QMouseEvent

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot.rois import ROICircle
from pcot.ui.roiedit import CircleEditor
from pcot.xform import xformtype, XFormROIType


def getInt(s):
    try:
        x = int(s)
    except ValueError:
        return -1
    return x


@xformtype
class XformCirc(XFormROIType):
    """
    Add a circular ROI to an image (see multidot for multiple circles). Can edit numerically.
    Most subsequent operations will only
    be performed on the union of all regions of interest.
    Also outputs an RGB image annotated with the ROI on the 'ann' RGB input, or the input
    image converted to RGB if that input is not connected.
    """

    def __init__(self):
        super().__init__("circle", "regions", "0.0.0")

    def createTab(self, n, w):
        return TabCirc(n, w)

    def init(self, node):
        node.img = None
        node.croprect = None  # would be (x,y,w,h) tuple
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.drawbg = True
        node.thickness = 2
        node.colour = (1, 1, 0)
        node.roi = ROICircle()
        node.roi.drawEdge = True

    def serialise(self, node):
        return node.roi.serialise()

    def deserialise(self, node, d):
        node.roi.deserialise(d)

    def setProps(self, node, img):
        node.roi.setContainingImageDimensions(img.w, img.h)
        node.roi.setDrawProps(node.captiontop, node.colour, node.fontsize, node.thickness, node.drawbg)

    def getMyROIs(self, node):
        return [node.roi]



class TabCirc(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabcirc.ui')
        self.editor = CircleEditor(self, self.node.roi)
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.drawbg.stateChanged.connect(self.drawbgChanged)
        self.w.thickness.valueChanged.connect(self.thicknessChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.captionTop.toggled.connect(self.topChanged)

        self.w.XEdit.editingFinished.connect(self.XEditChanged)
        self.w.YEdit.editingFinished.connect(self.YEditChanged)
        self.w.radiusEdit.editingFinished.connect(self.radiusEditChanged)

        validator = QIntValidator(0, 10000, w)
        self.w.XEdit.setValidator(validator)
        self.w.YEdit.setValidator(validator)
        self.w.radiusEdit.setValidator(validator)

        self.mouseDown = False
        self.dontSetText = False
        # sync tab with node
        self.nodeChanged()

    def drawbgChanged(self, val):
        self.mark()
        self.node.drawbg = (val != 0)
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

    def thicknessChanged(self, i):
        self.mark()
        self.node.thickness = i
        self.changed()

    def colourPressed(self):
        col = pcot.utils.colour.colDialog(self.node.colour)
        if col is not None:
            self.mark()
            self.node.colour = col
            self.changed()

    def roiSet(self, x, y, r):
        self.mark()
        self.node.roi.set(x, y, r)
        self.changed()

    def XEditChanged(self):
        c = self.node.roi.get()
        x, y, r = c if c is not None else (0, 0, 0)
        x = getInt(self.w.XEdit.text())
        self.roiSet(x, y, r)

    def YEditChanged(self):
        c = self.node.roi.get()
        x, y, r = c if c is not None else (0, 0, 0)
        y = getInt(self.w.XEdit.text())
        self.roiSet(x, y, r)

    def radiusEditChanged(self):
        c = self.node.roi.get()
        x, y, r = c if c is not None else (0, 0, 0)
        r = getInt(self.w.radiusEdit.text())
        self.roiSet(x, y, r)

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
        self.w.fontsize.setValue(self.node.fontsize)
        self.w.thickness.setValue(self.node.thickness)
        self.w.captionTop.setChecked(self.node.captiontop)
        self.w.drawbg.setChecked(self.node.drawbg)
        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));
        c = self.node.roi.get()
        if c is not None:
            x, y, r = [str(x) for x in c]
            self.w.XEdit.setText(x)
            self.w.YEdit.setText(y)
            self.w.radiusEdit.setText(r)

    def canvasMouseMoveEvent(self, x, y, e):
        self.editor.canvasMouseMoveEvent(x, y, e)

    def canvasMousePressEvent(self, x, y, e):
        self.editor.canvasMousePressEvent(x, y, e)

    def canvasMouseReleaseEvent(self, x, y, e):
        self.editor.canvasMouseReleaseEvent(x, y, e)
