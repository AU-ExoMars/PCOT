import math

from PySide2.QtCore import Qt
from PySide2.QtGui import QIntValidator, QMouseEvent

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot.rois import ROICircle
from pcot.ui.roiedit import CircleEditor
from pcot.utils.taggedaggregates import TaggedDictType, TaggedDict
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
        # see XFormRect for this.
        t = [(k, v) for k, v in ROICircle.TAGGEDDICTDEFINITION if k != "type"]
        self.params = TaggedDictType(*t)

    def createTab(self, n, w):
        return TabCirc(n, w)

    def init(self, node):
        node.croprect = None  # would be (x,y,w,h) tuple
        node.roi = ROICircle()

    def serialise(self, node):
        node.params = TaggedDict(self.params)
        # serialise the ROI into a TaggedDict, and copy fields from that into the node.params we just made.
        rser = node.roi.serialise()
        for k in node.params.keys():
            node.params[k] = rser[k]
        # the caller will use node.params.
        return None

    def deserialise(self, node, d):
        # deserialise the ROI from node.params, ignoring the dictionary passed in
        # because we don't do any "old style" direct serialisation to JSON
        node.roi.deserialise(node.params)

    def setProps(self, node, img):
        node.roi.setContainingImageDimensions(img.w, img.h)

    def getMyROIs(self, node):
        return [node.roi]


class TabCirc(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabcirc.ui')
        self.editor = CircleEditor(self)
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
        self.node.roi.drawbg = (val != 0)
        self.changed()

    def topChanged(self, checked):
        self.mark()
        self.node.roi.captiontop = checked
        self.changed()

    def fontSizeChanged(self, i):
        self.mark()
        self.node.roi.fontsize = i
        self.changed()

    def textChanged(self, t):
        self.mark()
        self.node.roi.caption = t
        # this will cause perform, which will cause onNodeChanged, which will
        # set the text again. We set a flag to stop the text being reset.
        self.dontSetText = True
        self.changed()
        self.dontSetText = False

    def thicknessChanged(self, i):
        self.mark()
        self.node.roi.thickness = i
        self.changed()

    def colourPressed(self):
        col = pcot.utils.colour.colDialog(self.node.roi.colour)
        if col is not None:
            self.mark()
            self.node.roi.colour = col
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
        y = getInt(self.w.YEdit.text())
        self.roiSet(x, y, r)

    def radiusEditChanged(self):
        c = self.node.roi.get()
        x, y, r = c if c is not None else (0, 0, 0)
        r = getInt(self.w.radiusEdit.text())
        self.roiSet(x, y, r)

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        self.w.canvas.setROINode(self.node)
        self.w.canvas.display(self.node.getOutput(XFormROIType.OUT_IMG))
        roi = self.node.roi
        if not self.dontSetText:
            self.w.caption.setText(roi.caption)
        self.w.fontsize.setValue(roi.fontsize)
        self.w.thickness.setValue(roi.thickness)
        self.w.captionTop.setChecked(roi.captiontop)
        self.w.drawbg.setChecked(roi.drawbg)
        r, g, b = [x * 255 for x in roi.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));
        c = roi.get()
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
