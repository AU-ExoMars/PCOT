import cv2 as cv
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QMessageBox

import pcot.conntypes as conntypes
import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text

from pcot.pancamimage import ImageCube, ROI, ROIPoly
from pcot.xform import xformtype, XFormType, Datum


@xformtype
class XformPoly(XFormType):
    """Add a polygonal ROI to an image.
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
        super().__init__("poly", "regions", "0.0.0")
        self.addInputConnector("input", conntypes.IMG)
        self.addInputConnector("ann", conntypes.IMGRGB, "used as base for annotated image")
        self.addOutputConnector("img", conntypes.IMG, "image with ROI")  # image+roi
        self.addOutputConnector("ann", conntypes.IMGRGB,
                                "image as RGB with ROI, with added annotations around ROI")  # annotated image
        self.addOutputConnector("rect", conntypes.RECT, "the crop rectangle data")  # rectangle (just the ROI's bounding box)
        self.autoserialise = ('caption', 'captiontop', 'fontsize', 'fontline', 'colour', 'drawMode')

    def createTab(self, n, w):
        return TabPoly(n, w)

    def init(self, node):
        node.img = None
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.fontline = 2
        node.colour = (1, 1, 0)
        node.drawMode = 0

        # initialise the ROI data, which will consist of a bounding box within the image and
        # a 2D boolean map of pixels within the image - True pixels are in the ROI.

        node.roi = ROIPoly()

    def serialise(self, node):
        return node.roi.serialise()

    def deserialise(self, node, d):
        node.roi.deserialise(d)

    def perform(self, node):
        img = node.getInput(self.IN_IMG, conntypes.IMG)
        inAnnot = node.getInput(self.IN_ANNOT, conntypes.IMG)
        # label the ROI
        node.roi.label = node.caption
        node.setRectText(node.caption)

        if img is None:
            node.roi.clear()
            # no image
            node.setOutput(self.OUT_IMG, None)
            node.setOutput(self.OUT_ANNOT, None if inAnnot is None else Datum(conntypes.IMGRGB, inAnnot))
            node.setOutput(self.OUT_RECT, None)
        else:
            node.roi.setImageSize(img.w, img.h)
            if node.drawMode == 0:
                drawPoints = True
                drawBox = True
            elif node.drawMode == 1:
                drawPoints = True
                drawBox = False
            else:
                drawPoints = False
                drawBox = False

            node.roi.setDrawProps(node.colour, node.fontsize, node.fontline, drawPoints, drawBox)

            # for the annotated image, we just get the RGB for the image in the
            # input node.
            img = img.copy()
            img.setMapping(node.mapping)
            rgb = img.rgbImage() if inAnnot is None else inAnnot.copy()
            bb = node.roi.bb()
            # now make an annotated image by drawing on the RGB image we got earlier
            # Note how this differs from some other ROIs - we might not have a BB, but still need to draw
            node.roi.draw(rgb)
            node.rgbImage = rgb  # the RGB image shown in the canvas (using the "premapping" idea)
            node.setOutput(self.OUT_ANNOT, Datum(conntypes.IMG, rgb))
            if bb is None:
                node.img = img  # the original image
                node.setOutput(self.OUT_RECT, None)
            else:
                # need to generate image + ROI
                # output image same as input image with same
                # ROIs. I could just pass input to output, but this would
                # mess things up if we go back up the tree again - it would
                # potentially modify the image we passed in.
                o = img.copy()
                o.rois.append(node.roi)  # and add to the image
                node.rgbImage.rois = o.rois  # with same ROI list as unannotated image
                # but we still store the original
                node.img = img
                # and the BB rectangle
                node.setOutput(self.OUT_RECT, Datum(conntypes.RECT, bb))

            if node.isOutputConnected(self.OUT_IMG):
                node.setOutput(self.OUT_IMG, Datum(conntypes.IMG, node.img))  # output image and ROI


class TabPoly(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabpoly.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook = self
        self.w.canvas.mouseHook = self
        self.w.canvas.keyHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.clearButton.pressed.connect(self.clearPressed)
        self.w.captionTop.toggled.connect(self.topChanged)
        self.w.drawMode.currentIndexChanged.connect(self.drawModeChanged)
        self.w.canvas.setGraph(node.graph)
        # but we still need to be able to edit it
        self.w.canvas.setMapping(node.mapping)

        self.mouseDown = False
        self.dontSetText = False
        # sync tab with node
        self.onNodeChanged()

    def drawModeChanged(self, idx):
        self.node.drawMode = idx
        self.changed()

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

    def clearPressed(self):
        if QMessageBox.question(self.parent(), "Clear region", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.node.roi.clear()
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
        self.w.drawMode.setCurrentIndex(self.node.drawMode)
        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

    # extra drawing!
    def canvasPaintHook(self, p):
        # we could draw the rectangle in here (dividing all sizes down by the canvas scale)
        # but it's more accurate done as above in onNodeChanged
        pass

    def canvasMouseMoveEvent(self, x, y, e):
        if self.mouseDown:
            if self.node.roi.moveSelPoint(x, y):
                self.changed()

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        if e.modifiers() & Qt.ShiftModifier:
            self.node.roi.addPoint(x, y)
        else:
            self.node.roi.selPoint(x, y)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False

    def canvasKeyPressEvent(self, e):
        self.node.roi.delSelPoint()
        self.changed()
