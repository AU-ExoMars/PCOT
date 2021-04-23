import cv2 as cv
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QMessageBox

import pcot.conntypes as conntypes
import pcot.ui.tabs
import pcot.utils.colour
import pcot.utils.text

from pcot.pancamimage import ImageCube, ROI
from pcot.xform import xformtype, XFormType, Datum


## a polygon ROI

class ROIPoly(ROI):
    def __init__(self):
        self.imgw = None
        self.imgh = None
        self.points = []
        self.selectedPoint = None

    def clear(self):
        self.points = []
        self.selectedPoint = None

    def hasPoly(self):
        return len(self.points) > 2

    def setImageSize(self, imgw, imgh):
        if self.imgw is not None:
            if self.imgw != imgw or self.imgh != imgh:
                self.clear()

        self.imgw = imgw
        self.imgh = imgh

    def bb(self):
        if not self.hasPoly():
            return None

        xmin = min([p[0] for p in self.points])
        xmax = max([p[0] for p in self.points])
        ymin = min([p[1] for p in self.points])
        ymax = max([p[1] for p in self.points])

        return xmin, ymin, xmax - xmin, ymax - ymin

    def serialise(self):
        return {
            'points': self.points,
        }

    def deserialise(self, d):
        if 'points' in d:
            pts = d['points']
            # points will be saved as lists, turn back into tuples
            self.points = [tuple(x) for x in pts]

    def mask(self):
        # return a boolean array, same size as BB. We use opencv here to build a uint8 image
        # which we convert into a boolean array.

        if not self.hasPoly():
            return

        # First, we need to build a polygon relative to the bounding box
        xmin, ymin, w, h = self.bb()
        poly = [(x - xmin, y - ymin) for (x, y) in self.points]

        # now create an empty image
        polyimg = np.zeros((h, w), dtype=np.uint8)
        # draw the polygon in it (we have enough points)
        pts = np.array(poly, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv.fillPoly(polyimg, [pts], 255)
        # convert to boolean
        return polyimg > 0

    def draw(self, img, colour, thickness, drawPoints):
        # first write the points in the actual image
        if drawPoints:
            for p in self.points:
                cv.circle(img, p, 7, colour, thickness)

        if self.selectedPoint is not None:
            if self.selectedPoint >= len(self.points):
                self.selectedPoint = None
            else:
                p = self.points[self.selectedPoint]
                cv.circle(img, p, 10, colour, thickness + 1)

        if not self.hasPoly():
            return

        # draw the polygon
        pts = np.array(self.points, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv.polylines(img, [pts], True, colour, thickness=thickness)

    def addPoint(self, x, y):
        self.points.append((x, y))

    def selPoint(self, x, y):
        mindist = None
        self.selectedPoint = None
        for idx in range(len(self.points)):
            p = self.points[idx]
            dx = p[0] - x
            dy = p[1] - y
            dsq = dx * dx + dy * dy
            print(dsq)
            if dsq < 1000 and (mindist is None or dsq < mindist):
                self.selectedPoint = idx
                mindist = dsq

    def moveSelPoint(self, x, y):
        if self.selectedPoint is not None:
            self.points[self.selectedPoint] = (x, y)
            return True
        else:
            return False

    def delSelPoint(self):
        if self.selectedPoint is not None:
            del self.points[self.selectedPoint]
            self.selectedPoint = None
            return True
        else:
            return False

    def __str__(self):
        if not self.hasPoly():
            return "ROI-POLY (no points)"
        x, y, w, h = self.bb()
        return "ROI-POLY {} {} {}x{}".format(x, y, w, h)


@xformtype
class XformPoly(XFormType):
    """Add a polygonal ROI to an image."""

    # constants enumerating the outputs
    OUT_IMG = 0
    OUT_CROP = 1
    OUT_ANNOT = 2
    OUT_RECT = 3

    def __init__(self):
        super().__init__("poly", "regions", "0.0.0")
        self.addInputConnector("", "img")
        self.addOutputConnector("img", "img", "image with ROI")  # image+roi
        self.addOutputConnector("crop", "img", "image cropped to ROI")  # cropped image
        self.addOutputConnector("ann", "img",
                                "image as RGB with ROI, with added annotations around ROI")  # annotated image
        self.addOutputConnector("rect", "rect", "the crop rectangle data")  # rectangle (just the ROI's bounding box)
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
        img = node.getInput(0, conntypes.IMG)
        if img is None:
            node.roi.clear()
            # no image
            node.setOutput(self.OUT_IMG, None)
            node.setOutput(self.OUT_CROP, None)
            node.setOutput(self.OUT_ANNOT, None)
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

            # for the annotated image, we just get the RGB for the image in the
            # input node.
            img = img.copy()
            img.setMapping(node.mapping)
            rgb = img.rgbImage()
            bb = node.roi.bb()
            # now make an annotated image by drawing on the RGB image we got earlier
            annot = rgb.img
            # Note how this differs from some other ROIs - we might not have a BB, but still need to draw
            node.roi.draw(annot, node.colour, node.fontline, drawPoints)
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

                # Write the bounding box. I may remove this.
                # We MUST WRITE OUTSIDE THE BOUNDS, otherwise we interfere
                # with the image! Doing this predictably with the thickness function
                # in cv.rectangle is a pain, so I'm doing it by hand.
                x, y, w, h = bb
                if drawBox:
                    for i in range(node.fontline):
                        cv.rectangle(annot, (x - i - 1, y - i - 1), (x + w + i, y + h + i), node.colour, thickness=1)

                # write the caption
                ty = y if node.captiontop else y + h
                pcot.utils.text.write(annot, node.caption, x, ty, node.captiontop, node.fontsize,
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
