import cv2 as cv

import cv2 as cv

import conntypes
import ui.canvas
import ui.tabs
import utils.colour
import utils.text
from pancamimage import ImageCube, ROIRect, ChannelMapping
from xform import xformtype, XFormType, Datum


@xformtype
class XformRect(XFormType):
    """Add a rectangular ROI to an image. At the next node all ROIs will be grouped together,
    used to perform the operation, and discarded."""

    # constants enumerating the outputs
    OUT_IMG = 0
    OUT_CROP = 1
    OUT_ANNOT = 2
    OUT_RECT = 3

    def __init__(self):
        super().__init__("rect", "regions", "0.0.0")
        self.addInputConnector("", "img")
        self.addOutputConnector("img", "img", "image with ROI")  # image+roi
        self.addOutputConnector("crop", "img", "image cropped to ROI")  # cropped image
        self.addOutputConnector("ann", "img",
                                "image as RGB with ROI, with added annotations around ROI")  # annotated image
        self.addOutputConnector("rect", "rect", "the rectangle data")  # rectangle (just the ROI)
        self.autoserialise = ('croprect', 'caption', 'captiontop', 'fontsize', 'fontline', 'colour')

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

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        if img is None:
            # no image
            node.setOutput(self.OUT_IMG, None)
            node.setOutput(self.OUT_CROP, None)
            node.setOutput(self.OUT_ANNOT, None)
            node.setOutput(self.OUT_RECT, None)
        else:
            # for the annotated image, we just get the RGB for the image in the
            # input node.
            img = img.copy()
            img.setMapping(node.mapping)
            rgb = img.rgbImage()
            if node.croprect is None:
                # no rectangle, but we still need to use the RGB for annotation
                node.rgbImage = rgb  # the RGB image shown in the canvas (using the "premapping" idea)
                node.img = img  # the original image
                node.setOutput(self.OUT_IMG, Datum(conntypes.IMG, img))
                node.setOutput(self.OUT_CROP, Datum(conntypes.IMG, img))
                node.setOutput(self.OUT_ANNOT, Datum(conntypes.IMG, rgb))
                node.setOutput(self.OUT_RECT, None)
            else:
                # need to generate image + ROI
                x, y, w, h = node.croprect
                # output image same as input image with same
                # ROIs. I could just pass input to output, but this would
                # mess things up if we go back up the tree again - it would
                # potentially modify the image we passed in.
                o = img.copy()
                roi = ROIRect(x, y, w, h)  # create the ROI
                o.rois.append(roi)  # and add to the image
                if node.isOutputConnected(self.OUT_IMG):
                    node.setOutput(0, Datum(conntypes.IMG, o))  # output image and ROI
                if node.isOutputConnected(self.OUT_CROP):
                    # output cropped image: this uses the ROI rectangle to
                    # crop the image; we get a numpy image out which we wrap.
                    # with no ROIs
                    node.setOutput(self.OUT_CROP,
                                   Datum(conntypes.IMG, ImageCube(roi.crop(o), node.mapping, o.sources)))

                # now make an annotated image by drawing on the RGB image we got earlier
                annot = rgb.img
                # write on it - but we MUST WRITE OUTSIDE THE BOUNDS, otherwise we interfere
                # with the image! Doing this predictably with the thickness function
                # in cv.rectangle is a pain, so I'm doing it by hand.
                for i in range(node.fontline):
                    cv.rectangle(annot, (x - i - 1, y - i - 1), (x + w + i, y + h + i), node.colour, thickness=1)

                ty = y if node.captiontop else y + h
                utils.text.write(annot, node.caption, x, ty, node.captiontop, node.fontsize,
                                 node.fontline, node.colour)
                # that's also the image displayed in the tab
                node.rgbImage = rgb
                node.rgbImage.rois = o.rois  # with same ROI list as unannotated image
                # but we still store the original
                node.img = img
                # output the annotated image
                node.setOutput(self.OUT_ANNOT, Datum(conntypes.IMG, node.rgbImage))
                # and the raw cropped rectangle
                node.setOutput(self.OUT_RECT, Datum(conntypes.RECT, node.croprect))


class TabRect(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabrect.ui')
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
        self.w.canvas.redisplayNode = node

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
        col = utils.colour.colDialog(self.node.colour)
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
            x, y, w, h = self.node.croprect
            w = x2 - x
            h = y2 - y
            if w < 10:
                w = 10
            if h < 10:
                h = 10
            self.node.croprect = (x, y, w, h)
            self.changed()
        self.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        p = e.pos()
        w = 10  # min crop size
        h = 10
        self.mouseDown = True
        self.node.croprect = (x, y, w, h)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
