import cv2 as cv
import numpy as np
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QMessageBox

import conntypes
import ui.tabs
import utils.colour
import utils.text
from scipy import ndimage
from pancamimage import ImageCube, ROI
from xform import xformtype, XFormType, Datum


## a "painted" ROI

class ROIPainted(ROI):
    def __init__(self):
        self.bbrect = None
        self.map = None
        self.img = None

    def clear(self):
        self.map = None
        self.bbrect = None

    def setImage(self, img):
        self.img = img

    def bb(self):
        return self.bbrect

    def serialise(self):
        return {
            'rect': self.bbrect,
            'map': self.map
        }

    def deserialise(self, d):
        if 'map' in d:
            self.map = d['map']
            self.bbrect = d['rect']

    def mask(self):
        # return a boolean array, same size as BB
        return self.map > 0

    def draw(self, img, colour, drawEdge):
        # draw into an RGB image
        # first, get the slice into the real image
        x, y, w, h = self.bb()
        imgslice = img[y:y + h, x:x + w]

        # now get the mask and run sobel edge-detection on it if required
        mask = self.mask()
        if drawEdge:
            sx = ndimage.sobel(mask, axis=0, mode='constant')
            sy = ndimage.sobel(mask, axis=1, mode='constant')
            mask = np.hypot(sx, sy)

        # flatten and repeat each element of the mask for each channel
        x = np.repeat(np.ravel(mask), 3)
        # and reshape into the same shape as the image slice
        x = np.reshape(x, imgslice.shape)

        # write a colour
        np.putmask(imgslice, x, colour)

    ## fill a circle in the ROI, or clear it (if delete is true)
    def setCircle(self, x, y, brushSize, delete=False):
        if self.img is not None:
            # There's a clever way of doing this I'm sure, but I'm going to do it the dumb way.
            # 1) create a map the size of the image and put the existing ROI into it
            # 2) extend the ROI with a new circle, just drawing it into the image
            # 3) crop the image back down again by finding a new bounding box and cutting the mask out of it.
            # It should hopefully be fast enough.

            # create full size map
            fullsize = np.zeros((self.img.w, self.img.h))
            # splice in existing data, if there is any!
            if self.bbrect is not None:
                bbx, bby, bbw, bbh = self.bbrect
                fullsize[bby:bby + bbh, bbx:bbx + bbw] = self.map
            # add the new circle
            r = int(getRadiusFromSlider(brushSize, self.img))
            cv.circle(fullsize, (x, y), r, 0 if delete else 255, -1)
            # calculate new bounding box
            cols = np.any(fullsize, axis=0)
            rows = np.any(fullsize, axis=1)
            ymin, ymax = np.where(rows)[0][[0, -1]]
            xmin, xmax = np.where(cols)[0][[0, -1]]
            xmax += 1
            ymax += 1
            # cut out the new data
            self.map = fullsize[ymin:ymax, xmin:xmax]
            # construct the new BB
            self.bbrect = (int(xmin), int(ymin), int(xmax - xmin), int(ymax - ymin))

    def __str__(self):
        if not self.bbrect:
            return "ROI-PAINTED (no points)"
        return "ROI-PAINTED {} {} {}x{}".format(self.bbrect.x, self.bbrect.y, self.bbrect.w, self.bbrect.h)


def getRadiusFromSlider(sliderVal, img):
    v = max(img.w,img.h)
    return (v/400) * sliderVal


@xformtype
class XFormPainted(XFormType):
    """Add a painted ROI to an image."""

    # constants enumerating the outputs
    OUT_IMG = 0
    OUT_CROP = 1
    OUT_ANNOT = 2
    OUT_RECT = 3

    def __init__(self):
        super().__init__("painted", "regions", "0.0.0")
        self.addInputConnector("", "img")
        self.addOutputConnector("img", "img", "image with ROI")  # image+roi
        self.addOutputConnector("crop", "img", "image cropped to ROI")  # cropped image
        self.addOutputConnector("ann", "img",
                                "image as RGB with ROI, with added annotations around ROI")  # annotated image
        self.addOutputConnector("rect", "rect", "the crop rectangle data")  # rectangle (just the ROI's bounding box)
        self.autoserialise = ('caption', 'captiontop', 'fontsize', 'fontline', 'colour', 'brushSize', 'drawMode')

    def createTab(self, n, w):
        return TabPainted(n, w)

    def init(self, node):
        node.img = None
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.fontline = 2
        node.colour = (1, 1, 0)
        node.brushSize = 20  # scale of 0-99 i.e. a slider value. Converted to pixel radius in getRadiusFromSlider()
        node.previewRadius = None  # previewing needs the image, but that's awkward - so we stash this data in perform()
        node.drawMode = 0

        # initialise the ROI data, which will consist of a bounding box within the image and
        # a 2D boolean map of pixels within the image - True pixels are in the ROI.

        node.roi = ROIPainted()

    def serialise(self, node):
        return node.roi.serialise()

    def deserialise(self, node, d):
        node.roi.deserialise(d)

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        node.roi.setImage(img)

        if node.drawMode == 0:
            drawEdge = True
            drawBox = True
        elif node.drawMode == 1:
            drawEdge = True
            drawBox = False
        elif node.drawMode == 2:
            drawEdge = False
            drawBox = True
        else:
            drawEdge = False
            drawBox = False

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
            bb = node.roi.bb()
            node.previewRadius = getRadiusFromSlider(node.brushSize,img)
            if bb is None:
                # no ROI, but we still need to use the RGB
                node.rgbImage = rgb  # the RGB image shown in the canvas (using the "premapping" idea)
                node.img = img  # the original image
                node.setOutput(self.OUT_IMG, Datum(conntypes.IMG, img))
                node.setOutput(self.OUT_CROP, Datum(conntypes.IMG, img))
                node.setOutput(self.OUT_ANNOT, Datum(conntypes.IMG, rgb))
                node.setOutput(self.OUT_RECT, None)
            else:
                # need to generate image + ROI

                # output image same as input image with same
                # ROIs. I could just pass input to output, but this would
                # mess things up if we go back up the tree again - it would
                # potentially modify the image we passed in.
                o = img.copy()
                o.rois.append(node.roi)  # and add to the image
                if node.isOutputConnected(self.OUT_IMG):
                    node.setOutput(0, Datum(conntypes.IMG, o))  # output image and ROI
                if node.isOutputConnected(self.OUT_CROP):
                    # output cropped image: this uses the ROI rectangle to
                    # crop the image; we get a numpy image out which we wrap.
                    # with no ROIs
                    node.setOutput(self.OUT_CROP,
                                   Datum(conntypes.IMG, ImageCube(node.roi.crop(o), node.mapping, o.sources)))

                # now make an annotated image by drawing on the RGB image we got earlier
                annot = rgb.img
                # Write the bounding box. I may remove this.
                # We MUST WRITE OUTSIDE THE BOUNDS, otherwise we interfere
                # with the image! Doing this predictably with the thickness function
                # in cv.rectangle is a pain, so I'm doing it by hand.
                x, y, w, h = bb
                if drawBox:
                    for i in range(node.fontline):
                        cv.rectangle(annot, (x - i - 1, y - i - 1), (x + w + i, y + h + i), node.colour, thickness=1)

                node.roi.draw(annot, node.colour, drawEdge)

                # write the caption
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
                # and the BB rectangle
                node.setOutput(self.OUT_RECT, Datum(conntypes.RECT, bb))


class TabPainted(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabpainted.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook = self
        self.w.canvas.mouseHook = self
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.fontline.valueChanged.connect(self.fontLineChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.clearButton.pressed.connect(self.clearPressed)
        self.w.captionTop.toggled.connect(self.topChanged)
        self.w.drawMode.currentIndexChanged.connect(self.drawModeChanged)
        self.w.brushSize.valueChanged.connect(self.brushSizeChanged)
        self.w.canvas.setGraph(node.graph)
        # but we still need to be able to edit it
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.canvas.setMouseTracking(True)
        self.mousePos = None
        self.mouseDown = False
        self.dontSetText = False
        # sync tab with node
        self.onNodeChanged()

    def drawModeChanged(self, idx):
        self.node.drawMode = idx
        self.changed()

    def brushSizeChanged(self, val):
        self.node.brushSize = val
        self.changed()

    def topChanged(self, checked):
        self.node.captiontop = checked
        self.changed()

    def fontSizeChanged(self, i):
        self.node.fontsize = i
        self.changed()

    def clearPressed(self):
        if QMessageBox.question(self.parent(), "Clear region", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.node.roi.clear()
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
        self.w.brushSize.setValue(self.node.brushSize)
        self.w.drawMode.setCurrentIndex(self.node.drawMode)

        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b));

    # extra drawing! Preview of brush
    def canvasPaintHook(self, p: QPainter):
        c = self.w.canvas
        if self.mousePos is not None and self.node.previewRadius is not None:
            p.setPen(QColor(*[v * 255 for v in self.node.colour]))
            r = self.node.previewRadius / (self.w.canvas.canvas.getScale())
            p.drawEllipse(self.mousePos, r, r)

    def doSet(self, x, y, e):
        if e.modifiers() & Qt.ShiftModifier:
            self.node.roi.setCircle(x, y, self.node.brushSize, True)  # delete
        else:
            self.node.roi.setCircle(x, y, self.node.brushSize, False)

    def canvasMouseMoveEvent(self, x, y, e):
        self.mousePos = e.pos()
        if self.mouseDown:
            self.doSet(x, y, e)
            self.changed()
        self.w.canvas.update()

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        self.doSet(x, y, e)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
