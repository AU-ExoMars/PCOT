from PySide2.QtGui import QIntValidator

import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot.rois import ROIRect
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

    def createTab(self, n, w):
        return TabRect(n, w)

    def init(self, node):
        node.img = None
        node.croprect = None  # would be (x,y,w,h) tuple
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.drawbg = True
        node.fontline = 2
        node.colour = (1, 1, 0)
        node.roi = ROIRect()

    def serialise(self, node):
        return node.roi.serialise()

    def deserialise(self, node, d):
        node.roi.deserialise(d)

    def setProps(self, node, img):
        node.roi.setDrawProps(node.captiontop, node.colour, node.fontsize, node.fontline, node.drawbg)

    def getMyROIs(self, node):
        return [node.roi]


class TabRect(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabrect.ui')
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.drawbg.stateChanged.connect(self.drawbgChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
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

    def roiSet(self,x,y,w,h):
        self.mark()
        self.node.roi.set(x,y,w,h)
        self.changed()

    def leftEditChanged(self):
        bb = self.node.roi.bb()
        x, y, w, h = bb if bb is not None else (0,0,0,0)
        try:
            x = int(self.w.leftEdit.text())
        except ValueError:
            x = 0
        if self.node.img and x >= self.node.img.w:
            x = self.node.img.w - w
        self.roiSet(x, y, w, h)

    def topEditChanged(self):
        bb = self.node.roi.bb()
        x, y, w, h = bb if bb is not None else (0, 0, 0, 0)
        try:
            y = int(self.w.topEdit.text())
        except ValueError:
            y = 0
        if self.node.img and y >= self.node.img.h:
            y = self.node.img.h - h
        self.roiSet(x, y, w, h)

    def widthEditChanged(self):
        bb = self.node.roi.bb()
        x, y, w, h = bb if bb is not None else (0, 0, 0, 0)
        try:
            w = int(self.w.widthEdit.text())
        except ValueError:
            w = 1
        if self.node.img and x + w >= self.node.img.w:
            w = self.node.img.w - x
        self.roiSet(x, y, w, h)

    def heightEditChanged(self):
        bb = self.node.roi.bb()
        x, y, w, h = bb if bb is not None else (0, 0, 0, 0)
        try:
            h = int(self.w.heightEdit.text())
        except ValueError:
            h = 1
        if self.node.img and y + h >= self.node.img.h:
            h = self.node.img.h - y
        self.roiSet(x, y, w, h)

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
        self.w.fontline.setValue(self.node.fontline)
        self.w.captionTop.setChecked(self.node.captiontop)
        self.w.drawbg.setChecked(self.node.drawbg)
        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));
        bb = self.node.roi.bb()
        if bb is not None:
            x, y, w, h = [str(x) for x in (bb.x, bb.y, bb.w, bb.h)]
            self.w.leftEdit.setText(x)
            self.w.topEdit.setText(y)
            self.w.widthEdit.setText(w)
            self.w.heightEdit.setText(h)

    # extra drawing!
    def canvasPaintHook(self, p):
        pass

    def canvasMouseMoveEvent(self, x2, y2, e):
        if self.mouseDown:
            bb = self.node.roi.bb()
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
            self.node.roi.set(x, y, w, h)
            self.changed()
        self.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        self.mark()
        self.node.roi.set(x, y, 5, 5)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
