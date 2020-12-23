import cv2 as cv
import numpy as np

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

import utils.text, utils.colour
import ui, ui.tabs, ui.canvas
from xform import xformtype, XFormType
from xforms.tabimage import TabImage
from pancamimage import Image


# this transform takes an image and places it at a position inside another image.
# The inset position is taken either from a control, or if this isn't present,
# from a rubberband selection as in xformcrop.

@xformtype
class XformInset(XFormType):
    """Inset an image inside another. Converts both images to RGB and does not honour regions of interest."""

    def __init__(self):
        super().__init__("inset", "regions", "0.0.0")
        self.addInputConnector("img", "img")
        self.addInputConnector("inset", "img")
        self.addInputConnector("rect", "rect")
        self.addOutputConnector("", "img")
        self.autoserialise = ('insetrect', 'caption', 'captiontop',
                              'fontsize', 'fontline', 'colour')
        self.hasEnable = True

    def createTab(self, n, w):
        return TabInset(n, w)

    def generateOutputTypes(self, node):
        node.matchOutputsToInputs([(0, 0)])

    def init(self, node):
        node.img = None
        node.insetrect = None
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.fontline = 2
        node.colour = (1, 1, 0)

    def perform(self, node):
        image = node.getInput(0)
        inset = node.getInput(1)
        inrect = node.getInput(2)

        # if there is no input rect we use the rubberbanded one set by the tab
        if inrect is None:
            inrect = node.insetrect

        if inrect is None:
            # neither rects are set, just dupe the input
            if image is None:
                out = None
            else:
                out = image.img
        elif image is None:
            # if there's no image we can't put anything on it.
            out = None
        else:
            x, y, w, h = inrect  # get the rectangle
            out = image.rgb().copy()  # get a numpy array copy of outer image as RGB
            if inset is None:
                # there's no inset image, draw a rectangle
                cv.rectangle(out, (x, y), (x + w, y + h), (0, 0, 255), -1)  # -1=filled
            elif node.enabled:  # only add the inset if enabled
                # resize the inset (and cvt to RGB if necessary)
                t = cv.resize(inset.rgb(), dsize=(w, h), interpolation=cv.INTER_AREA)
                out[y:y + h, x:x + w] = t

            # sources could now be multiple images in each channel
            sources = Image.buildSources([image, inset])
            for i in range(node.fontline):
                cv.rectangle(out, (x - i - 1, y - i - 1), (x + w + i, y + h + i), node.colour, thickness=1)
            # add in the caption
            if node.caption != '':
                print(node.captiontop)
                ty = y if node.captiontop else y + h
                utils.text.write(out, node.caption, x, ty, node.captiontop, node.fontsize,
                                 node.fontline, node.colour)

        node.img = None if out is None else Image(out, sources)
        node.setOutput(0, node.img)


class TabInset(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabinset.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook = self
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.captionTop.toggled.connect(self.topChanged)
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
        # we just draw the composited image
        if self.node.img is not None:
            self.w.canvas.display(self.node.img)
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
        self.mouseDown = True
        self.node.insetrect = (x, y, w, h)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
