from PySide2.QtGui import QIntValidator

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot import ui
from pcot.rois import ROIRect
from pcot.ui.roiedit import RectEditor
from pcot.utils.taggedaggregates import TaggedDict, TaggedDictType
from pcot.xform import xformtype, XFormROIType


@xformtype
class XformRect(XFormROIType):
    """
    Add a rectangular ROI to an image.
    Most subsequent operations will only
    be performed on the union of all regions of interest.
    Also outputs an RGB image annotated with the ROI on the 'ann' RGB input, or the input
    image converted to RGB if that input is not connected.
    """

    def __init__(self):
        super().__init__("rect", "regions", "0.0.0")
        # the parameters for this node are essentially the parameters for a ROIRect
        # but with "type" removed. This is because "type" is a key in both the ROI and
        # the XForm, and we're using the same dictionary to store both. It worked before
        # because a "rect" node always produces a "rect" ROI - they are always the same.
        # But it's messy. I would change it but back-compat is a thing.

        t = [(k, v) for k, v in ROIRect.TAGGEDDICTDEFINITION if k != "type"]
        self.params = TaggedDictType(*t)

    def createTab(self, n, w):
        return TabRect(n, w)

    def init(self, node):
        node.roi = ROIRect()

    def serialise(self, node):
        # this returns None, but stores data into .params ready for serialisation
        # Again - more hackery to get around ROI having 'type' and this clashing with node's 'type'
        node.params = TaggedDict(self.params)  # build a dict without the 'type' (see init)
        # Serialise the ROI into a TaggedDict, and copy fields from that into the node.params we just made.
        rser = node.roi.to_tagged_dict()
        for k in node.params.keys():
            node.params[k] = rser[k]
        # don't return anything; our return is essentially the
        # node.params
        return None

    def deserialise(self, node, d):
        # this deserialises data from .params into the node's ROI directly - it ignores the
        # dictionary passed in because we don't do any "old style" direct serialisation to JSON
        node.roi.from_tagged_dict(node.params)

    def setProps(self, node, img):
        node.roi.setContainingImageDimensions(img.w, img.h)

    def getMyROIs(self, node):
        return [node.roi]


class TabRect(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabrect.ui')
        self.editor = RectEditor(self)
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.drawbg.stateChanged.connect(self.drawbgChanged)
        self.w.thickness.valueChanged.connect(self.thicknessChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.captionTop.toggled.connect(self.topChanged)

        self.w.leftEdit.editingFinished.connect(self.leftEditChanged)
        self.w.topEdit.editingFinished.connect(self.topEditChanged)
        self.w.widthEdit.editingFinished.connect(self.widthEditChanged)
        self.w.heightEdit.editingFinished.connect(self.heightEditChanged)

        validator = QIntValidator(0, 10000, w)
        self.w.leftEdit.setValidator(validator)
        self.w.topEdit.setValidator(validator)
        self.w.widthEdit.setValidator(validator)
        self.w.heightEdit.setValidator(validator)

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
        self.node.roi.labeltop = checked
        self.changed()

    def fontSizeChanged(self, i):
        self.mark()
        self.node.roi.fontsize = i
        self.changed()

    def textChanged(self, t):
        self.mark()
        self.node.roi.label = t
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

    def roiSet(self, x, y, w, h):
        self.mark()
        self.node.roi.set(x, y, w, h)
        self.changed()

    def leftEditChanged(self):
        bb = self.node.roi.bb()
        img = self.node.getOutput(XFormROIType.OUT_IMG)
        x, y, w, h = bb if bb is not None else (0, 0, 0, 0)
        try:
            x = int(self.w.leftEdit.text())
        except ValueError:
            x = 0
        if img and x >= img.w:
            x = img.w - w
        self.roiSet(x, y, w, h)

    def topEditChanged(self):
        bb = self.node.roi.bb()
        img = self.node.getOutput(XFormROIType.OUT_IMG)
        x, y, w, h = bb if bb is not None else (0, 0, 0, 0)
        try:
            y = int(self.w.topEdit.text())
        except ValueError:
            y = 0
        if img and y >= img.h:
            y = img.h - h
        self.roiSet(x, y, w, h)

    def widthEditChanged(self):
        bb = self.node.roi.bb()
        img = self.node.getOutput(XFormROIType.OUT_IMG)
        x, y, w, h = bb if bb is not None else (0, 0, 0, 0)
        try:
            w = int(self.w.widthEdit.text())
        except ValueError:
            w = 1
        if img and x + w >= img.w:
            w = img.w - x
        self.roiSet(x, y, w, h)

    def heightEditChanged(self):
        bb = self.node.roi.bb()
        img = self.node.getOutput(XFormROIType.OUT_IMG)
        x, y, w, h = bb if bb is not None else (0, 0, 0, 0)
        try:
            h = int(self.w.heightEdit.text())
        except ValueError:
            h = 1
        if img and y + h >= img.h:
            h = h - y
        self.roiSet(x, y, w, h)

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setNode(self.node)
        self.w.canvas.setROINode(self.node)
        self.w.canvas.display(self.node.getOutput(XFormROIType.OUT_IMG))
        roi = self.node.roi
        if not self.dontSetText:
            self.w.caption.setText(roi.label)
        self.w.fontsize.setValue(roi.fontsize)
        self.w.thickness.setValue(roi.thickness)
        self.w.captionTop.setChecked(roi.labeltop)
        self.w.drawbg.setChecked(roi.drawbg)
        r, g, b = [x * 255 for x in roi.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b))
        bb = roi.bb()
        if bb is not None:
            x, y, w, h = [str(x) for x in (bb.x, bb.y, bb.w, bb.h)]
            self.w.leftEdit.setText(x)
            self.w.topEdit.setText(y)
            self.w.widthEdit.setText(w)
            self.w.heightEdit.setText(h)

    def canvasMouseMoveEvent(self, x, y, e):
        self.editor.canvasMouseMoveEvent(x, y, e)

    def canvasMousePressEvent(self, x, y, e):
        ui.log(f"node is {self.node}, ROI is {repr(self.node.roi)}")
        self.editor.canvasMousePressEvent(x, y, e)

    def canvasMouseReleaseEvent(self, x, y, e):
        self.editor.canvasMouseReleaseEvent(x, y, e)
