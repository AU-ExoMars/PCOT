import math

from PySide2.QtCore import Qt
from PySide2.QtGui import QIntValidator, QMouseEvent

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot.rois import ROICircle
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
        node.fontline = 2
        node.colour = (1, 1, 0)
        node.roi = ROICircle()
        node.roi.drawEdge = True

    def serialise(self, node):
        return node.roi.serialise()

    def deserialise(self, node, d):
        node.roi.deserialise(d)

    def setProps(self, node, img):
        node.roi.setDrawProps(node.captiontop, node.colour, node.fontsize, node.fontline, node.drawbg)

    def getMyROIs(self, node):
        return [node.roi]



class TabCirc(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabcirc.ui')
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.drawbg.stateChanged.connect(self.drawbgChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
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
        self.w.drawbg.setChecked(self.node.drawbg)
        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));
        c = self.node.roi.get()
        if c is not None:
            x, y, r = [str(x) for x in c]
            self.w.XEdit.setText(x)
            self.w.YEdit.setText(y)
            self.w.radiusEdit.setText(r)

    def setRadius(self, x2, y2):
        c = self.node.roi.get()
        x, y, r = c if c is not None else (0, 0, 0)
        dx = x - x2
        dy = y - y2
        r = math.sqrt(dx * dx + dy * dy)
        if r < 1:
            r = 1
        # we don't do a mark here to avoid multiple marks - one is done on mousedown.
        self.node.roi.set(x, y, r)
        self.changed()
        self.w.canvas.update()

    def canvasMouseMoveEvent(self, x2, y2, e):
        if self.mouseDown:
            self.setRadius(x2, y2)

    def canvasMousePressEvent(self, x, y, e: QMouseEvent):
        self.mouseDown = True
        self.mark()
        if e.button() == Qt.RightButton and self.node.roi.get() is not None:
            self.setRadius(x, y)
        else:
            if e.modifiers() & Qt.ShiftModifier and self.node.roi.get() is not None:
                _, _, r = self.node.roi.get()
            else:
                r = 10
            self.node.roi.set(x, y, r)
            self.changed()
            self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False

