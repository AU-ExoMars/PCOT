import cv2 as cv

import pcot.conntypes as conntypes
import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot.pancamimage import ImageCube, ROIRect, ChannelMapping
from pcot.xform import xformtype, XFormType, Datum, XFormROIType


@xformtype
class XformRect(XFormROIType):
    """Add a rectangular ROI to an image.
    At the next node all ROIs will be grouped together,
    used to perform the operation, and discarded.
    Also outputs an RGB image annotated with the ROI on the 'ann' RGB input, or the input
    image converted to RGB if that input is not connected.
    """

    # constants enumerating the outputs
    OUT_IMG = 0
    OUT_ANNOT = 1
    OUT_RECT = 2

    IN_IMG = 0
    IN_ANNOT = 1

    def __init__(self):
        super().__init__("rect", "regions", "0.0.0")
        self.addInputConnector("input", conntypes.IMG)
        self.addInputConnector("ann", conntypes.IMGRGB, "used as base for annotated image")
        self.addOutputConnector("img", conntypes.IMG, "image with ROI")  # image+roi
        self.addOutputConnector("ann", conntypes.IMGRGB,
                                "image as RGB with ROI, with added annotations around ROI")  # annotated image
        self.addOutputConnector("rect", conntypes.RECT, "the crop rectangle data")  # rectangle (just the ROI's bounding box)
        self.autoserialise = ('caption', 'captiontop', 'fontsize', 'fontline', 'colour')

    def createTab(self, n, w):
        return TabRect(n, w)

    def init(self, node):
        node.img = None
        node.croprect = None  # would be (x,y,w,h) tuple
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.fontline = 2
        node.colour = (1, 1, 0)
        node.roi = ROIRect()

    def serialise(self, node):
        return node.roi.serialise()

    def deserialise(self, node, d):
        node.roi.deserialise(d)

    def setProps(self, node, img):
        node.roi.setDrawProps(node.colour, node.fontsize, node.fontline)


class TabRect(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabrect.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook = self
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.captionTop.toggled.connect(self.topChanged)
        self.w.canvas.setGraph(node.graph)
        # but we still need to be able to edit it
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setPersister(node)

        self.mouseDown = False
        self.dontSetText = False
        # sync tab with node
        self.onNodeChanged()

    def topChanged(self, checked):
        self.node.captiontop = checked
        self.changed()

    def fontSizeChanged(self, i):
        self.node.fontsize = i
        self.changed()

    def textChanged(self, t):
        self.node.caption = t
        # this will cause perform, which will cause onNodeChanged, which will
        # set the text again. We set a flag to stop the text being reset.
        self.dontSetText = True
        self.changed()
        self.dontSetText = False

    def fontLineChanged(self, i):
        self.node.fontline = i
        self.changed()

    def colourPressed(self):
        col = pcot.utils.colour.colDialog(self.node.colour)
        if col is not None:
            self.node.colour = col
            self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
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
        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

    # extra drawing!
    def canvasPaintHook(self, p):
        # we could draw the rectangle in here (dividing all sizes down by the canvas scale)
        # but it's more accurate done as above in onNodeChanged
        pass

    def canvasMouseMoveEvent(self, x2, y2, e):
        if self.mouseDown:
            p = e.pos()
            x, y, w, h = self.node.roi.bb()
            w = x2 - x
            h = y2 - y
            if w < 10:
                w = 10
            if h < 10:
                h = 10
            self.node.roi.setBB(x, y, w, h)
            self.changed()
        self.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        p = e.pos()
        w = 10  # min crop size
        h = 10
        self.mouseDown = True
        self.node.roi.setBB(x, y, w, h)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
