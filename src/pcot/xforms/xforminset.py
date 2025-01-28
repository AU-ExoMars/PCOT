import cv2 as cv
from PySide2.QtWidgets import QMessageBox

from pcot.datum import Datum
import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text
from pcot.parameters.taggedaggregates import Maybe, taggedRectType, TaggedDictType, taggedColourType
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
    the input nodes.

    The rectangle can be set either from an ROI or from a rectangle which can be drawn on
    the canvas. If neither is set, no insetting will be done and only the background will
    be shown. The rectangle can be cleared by clicking "Clear rect" in the tab, but any ROI
    takes priority.

    **Ignores DQ and uncertainty**
    """

    def __init__(self):
        super().__init__("inset", "ROI edit", "0.0.0")
        self.addInputConnector("img", Datum.IMG)
        self.addInputConnector("inset", Datum.IMG)
        self.addInputConnector("roi", Datum.ROI)
        self.addOutputConnector("", Datum.IMG)

        self.params = TaggedDictType(
            # We don't use Maybe here, because batch files can't create the underlying TaggedDict, just modify
            # any existing one. Instead, we set the width and height to negative.
            insetrect=("The rectangle in which to inset the image", taggedRectType(0,0,-1,-1)),
            caption=("Caption to put on the inset", str, ''),
            captiontop=("Put the caption at the top of the inset", bool, False),
            fontsize=("Font size for the caption", int, 10),
            thickness=("Thickness of the border", int, 2),
            colour=("Colour of the border and caption", taggedColourType(1,1,0), None)
        )

    def createTab(self, n, w):
        return TabInset(n, w)

    def init(self, node):
        pass

    def perform(self, node):
        image = node.getInput(0, Datum.IMG)  # this is the main image
        inset = node.getInput(1, Datum.IMG)  # this is the thing we're going to insert
        roi = node.getInput(2, Datum.ROI)  # this is the ROI

        inrect = None if roi is None else roi.bb()  # get rect from ROI

        p = node.params

        # if there is no input rect we use the rubberbanded one set by the tab, and that defaults to negative
        # size meaning it doesn't exist.
        if inrect is None:
            inrect = p.insetrect
            # if the rectangle's size is negative, it's not set - so set it to None.
            if inrect.w < 0:
                inrect = None
            else:
                # otherwise create a tuple from the TaggedDict rectangle
                inrect = inrect.get()

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
            else:
                # resize the inset (and cvt to RGB if necessary); note that we're again
                # using the RGB mapping it should have been given in the previous node.
                insetrgb = inset.rgb()

                t = cv.resize(insetrgb, dsize=(w, h), interpolation=cv.INTER_AREA)
                out[y:y + h, x:x + w] = t
                # build sources - these will be bandwise unions of inset and background
                src = MultiBandSource.createBandwiseUnion([image.rgbSources(), inset.rgbSources()])

            for i in range(p.thickness):
                cv.rectangle(out, (x - i - 1, y - i - 1), (x + w + i, y + h + i), p.colour, thickness=1)
            # add in the caption
            if p.caption != '':
                ty = y if p.captiontop else y + h
                pcot.utils.text.write(out, p.caption, x, ty, p.captiontop, p.fontsize,
                                      p.thickness, p.colour)

        # build output image
        if out is None:
            img = None
        else:
            img = ImageCube(out, node.mapping, sources=src, rois=[roi] if roi else None)
        node.setOutput(0, Datum(Datum.IMG, img))


class TabInset(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabinset.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.thickness.valueChanged.connect(self.thicknessChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.clearRectButton.pressed.connect(self.clearRectPressed)
        self.w.captionTop.toggled.connect(self.topChanged)
        self.w.canvas.setGraph(node.graph)
        self.w.canvas.hideMapping()

        self.mouseDown = False
        self.dontSetText = False
        # sync tab with node
        self.nodeChanged()

    def topChanged(self, checked):
        self.mark()
        self.node.params.captiontop = checked
        self.changed()

    def fontSizeChanged(self, i):
        self.mark()
        self.node.params.fontsize = i
        self.changed()

    def textChanged(self, t):
        self.mark()
        self.node.params.caption = t
        # this will cause perform, which will cause onNodeChanged, which will
        # set the text again. We set a flag to stop the text being reset.
        self.dontSetText = True
        self.changed()
        self.dontSetText = False

    def thicknessChanged(self, i):
        self.mark()
        self.node.params.thickness = i
        self.changed()

    def colourPressed(self):
        col = pcot.utils.colour.colDialog(self.node.params.colour)
        if col is not None:
            self.mark()
            self.node.params.colour = col
            self.changed()

    def clearRectPressed(self):
        if QMessageBox.question(self.window, "Clear rectangle", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.mark()
            self.node.params.insetrect.set(0, 0, -1, -1)
            self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # we just draw the composited image
        img = self.node.getOutput(0, Datum.IMG)
        if img is not None:
            # have to do canvas set up here to handle extreme undo events which change the graph and nodes
            # TODO - not sure why we aren't doing the whole setNode here.
            self.w.canvas.setPersister(self.node)
            img.mapping = ChannelMapping(0,1,2)
            self.w.canvas.display(img)
        if not self.dontSetText:
            self.w.caption.setText(self.node.params.caption)
        self.w.fontsize.setValue(self.node.params.fontsize)
        self.w.thickness.setValue(self.node.params.thickness)
        self.w.captionTop.setChecked(self.node.params.captiontop)

        r, g, b = [x * 255 for x in self.node.params.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b))

    def canvasMouseMoveEvent(self, x2, y2, e):
        if self.mouseDown:
            x, y, w, h = self.node.params.insetrect.get()
            w = x2 - x
            h = y2 - y
            if w < 10:
                w = 10
            if h < 10:
                h = 10
            self.node.params.insetrect.set(x, y, w, h)
            self.changed()
        self.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        w = 10  # min crop size
        h = 10
        self.mark()
        self.mouseDown = True
        self.node.params.insetrect.set(x, y, w, h)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
