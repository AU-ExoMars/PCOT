import cv2 as cv

from pcot.datum import Datum
import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot.sources import MultiBandSource
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.xform import xformtype, XFormType


# this transform takes an image and places it at a position inside another image.
# The inset position is taken either from a control, or if this isn't present,
# from a rubberband selection as in xformcrop.

@xformtype
class XformInset(XFormType):
    """
    Inset an image inside another. Uses RGB versions of both images, as defined by the
    RGB mapping set in the previous nodes. Does not honour regions of interest. Note that
    there is no RGB mapping in the canvas for the tab - RGB mappings should be set in
    the input nodes."""

    def __init__(self):
        super().__init__("inset", "ROI edit", "0.0.0")
        self.addInputConnector("img", Datum.IMG)
        self.addInputConnector("inset", Datum.IMG)
        self.addInputConnector("roi", Datum.ROI)
        self.addOutputConnector("", Datum.IMG)
        self.autoserialise = ('insetrect', 'caption', 'captiontop',
                              'fontsize', 'fontline', 'colour')
        self.hasEnable = True

    def createTab(self, n, w):
        return TabInset(n, w)

    def init(self, node):
        node.img = None
        node.insetrect = None
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.fontline = 2
        node.colour = (1, 1, 0)

    def perform(self, node):
        image = node.getInput(0, Datum.IMG)  # this is the main image
        inset = node.getInput(1, Datum.IMG)  # this is the thing we're going to insert
        roi = node.getInput(2, Datum.ROI)  # this is the ROI

        inrect = None if roi is None else roi.bb()  # get rect from ROI

        # if there is no input rect we use the rubberbanded one set by the tab
        if inrect is None:
            inrect = node.insetrect

        if inrect is None:
            # neither rects are set, just dupe the input as RGB
            if image is None:
                out = None
                src = None
            else:
                # we're outputting only RGB, because nothing else really makes sense with
                # an inset. This will get the RGB image for the input, with which it was mapped
                # in the previous node.
                out = image.rgb()
                src = image.rgbSources()
        elif image is None:
            # if there's no image we can't put anything on it.
            out = None
            src = None
        else:
            x, y, w, h = inrect  # get the rectangle
            # Similarly, this will get the RGB for the image as mapped in the previous node.
            out = image.rgb()
            src = image.rgbSources()
            if inset is None:
                # there's no inset image, draw a rectangle
                cv.rectangle(out, (x, y), (x + w, y + h), (0, 0, 255), -1)  # -1=filled
            elif node.enabled:  # only add the inset if enabled
                # resize the inset (and cvt to RGB if necessary); note that we're again
                # using the RGB mapping it should have been given in the previous node.
                insetrgb = inset.rgb()

                t = cv.resize(insetrgb, dsize=(w, h), interpolation=cv.INTER_AREA)
                out[y:y + h, x:x + w] = t
                # build sources - these will be bandwise unions of inset and background
                src = MultiBandSource.createBandwiseUnion([image.rgbSources(), inset.rgbSources()])

            for i in range(node.fontline):
                cv.rectangle(out, (x - i - 1, y - i - 1), (x + w + i, y + h + i), node.colour, thickness=1)
            # add in the caption
            if node.caption != '':
                ty = y if node.captiontop else y + h
                pcot.utils.text.write(out, node.caption, x, ty, node.captiontop, node.fontsize,
                                 node.fontline, node.colour)

        # build output image
        node.img = None if out is None else ImageCube(out, node.mapping, sources=src)
        node.setOutput(0, Datum(Datum.IMG, node.img))


class TabInset(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabinset.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook = self
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.captionTop.toggled.connect(self.topChanged)
        self.w.canvas.setGraph(node.graph)
        # the image is always RGB, so we shouldn't be able to remap it
        self.w.canvas.setMapping(ChannelMapping(0, 1, 2))
        self.w.canvas.hideMapping()

        self.mouseDown = False
        self.dontSetText = False
        # sync tab with node
        self.nodeChanged()

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

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # we just draw the composited image
        if self.node.img is not None:
            # have to do canvas set up here to handle extreme undo events which change the graph and nodes
            self.w.canvas.setPersister(self.node)
            self.w.canvas.display(self.node.img)
        if not self.dontSetText:
            self.w.caption.setText(self.node.caption)
        self.w.fontsize.setValue(self.node.fontsize)
        self.w.fontline.setValue(self.node.fontline)
        self.w.captionTop.setChecked(self.node.captiontop)

        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b))

    # extra drawing!
    def canvasPaintHook(self, p):
        # we could draw the rectangle in here (dividing all sizes down by the canvas scale)
        # but it's more accurate done as above in onNodeChanged
        pass

    def canvasMouseMoveEvent(self, x2, y2, e):
        if self.mouseDown:
            p = e.pos()
            x, y, w, h = self.node.insetrect
            w = x2 - x
            h = y2 - y
            if w < 10:
                w = 10
            if h < 10:
                h = 10
            self.node.insetrect = (x, y, w, h)
            self.changed()
        self.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        p = e.pos()
        w = 10  # min crop size
        h = 10
        self.mark()
        self.mouseDown = True
        self.node.insetrect = (x, y, w, h)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
