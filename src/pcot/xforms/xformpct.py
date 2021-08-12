import numpy as np
from numpy.ma import masked

import pcot.conntypes as conntypes
import cv2 as cv

import pcot
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor, QPainter, QPolygon, QFont
from PyQt5.QtWidgets import QMessageBox
from pcot.calib import pct
from pcot.rois import getRadiusFromSlider, ROIPainted
from pcot.xform import xformtype, XFormType

# scale of editing brush
BRUSHSCALE = 0.1

class FloodFiller:
    def __init__(self, img):
        self.means = np.repeat(0, img.channels).astype(np.float64)
        self.img = img.img
        self.h, self.w = self.img.shape[:2]
        self.mask = np.zeros(self.img.shape[:2], dtype=np.bool)
        self.n = 0

    def _set(self, x, y):
        """set pixel and update cumulative moving means"""
        if not self.mask[y, x]:
            self.mask[y, x] = True
            self.means = (self.img[y, x] + self.n * self.means) / (self.n + 1)
            self.n += 1

    def fill(self, x, y, minpix=0, maxpix=10000):
        """Perform the fill, returning true if the number of pixels found
        was within an acceptable range (will exit early if too many)"""
        stack = [(x, y)]
        while stack:
            x, y = stack.pop()
            if self._inside(x, y):
                if self.n > maxpix:
                    return False
                self._set(x, y)
                stack.append((x - 1, y))
                stack.append((x + 1, y))
                stack.append((x, y - 1))
                stack.append((x, y + 1))
        if self.n < minpix:
            return False
        else:
            return True

    def _inside(self, x, y):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return False
        if self.mask[y, x]:
            return False
        # get the point we're talking about in the image
        # and see how far it is from the running mean
        if self.n > 0:
            dsq = np.sum((self.img[y, x] - self.means) ** 2)
            if dsq > 0.005:
                return False
        return True


def createPatchROI(n, x, y, radius):
    """Create a ROIPainted which encompasses the coords x,y. The patch has
    a given radius in mm, which we use to determine the min and max number
    of pixels acceptable."""

    # first step - create a bool mask the same size as the image, all zeroes.

    # second step - perform a flood fill of this mask, using the image itself
    # as a reference. Fill should stop when the point about to be filled is
    # very far from the mean of the points so far.

    ff = FloodFiller(n.img)
    # get minimum and maximum pixel sizes (empirically determined from radius of patch)
    maxPix = radius ** 2 * 4
    minPix = 0      # probably best to not have a min pixel count

    if ff.fill(int(x), int(y), minpix=minPix, maxpix=maxPix):
        # third step - crop down to a mask and BB, generate a ROIPainted and return.
        # can use the cropdown method in the ROI for this.
        roi = ROIPainted(mask=ff.mask)
        roi.cropDownWithDraw()

        # TEST - draw into image
        # n.img.img[ff.mask] = np.repeat(1, n.img.channels)
    else:
        roi = None
    print("Pixel range: [{},{}] : found {}, ROI={}".format(minPix, maxPix, ff.n, roi))
    return roi


@xformtype
class XformPCT(XFormType):
    """Locates the PCT and generates calibration coefficients"""

    def __init__(self):
        super().__init__("pct", "calibration", "0.0.0")
        self.addInputConnector("img", conntypes.IMG)
        self.autoserialise = ('brushSize', 'pctPoints', 'drawMode')
        # TODO output!

    def createTab(self, n, w):
        return TabPCT(n, w)

    def serialise(self, n):
        return {'rois': [None if roi is None else roi.serialise() for roi in n.rois]}

    def deserialise(self, n, d):
        n.rois = []
        if 'rois' in d:
            for ent in d['rois']:
                r = ROIPainted()
                r.deserialise(ent)
                n.rois.append(r)

    def init(self, node):
        node.img = None
        node.data = None
        node.rgbImage = None
        node.previewRadius = None  # previewing needs the image, but that's awkward - so we stash this data in perform()
        node.brushSize = 10
        node.drawMode = 'Fill'
        # (x,y) tuples for screen positions of screws; a deque so we can rotate
        node.pctPoints = []
        node.selPoint = -1  # selected point to move
        node.rois = []  # list of ROIs (ROIPainted); if none then we're editing points.
        node.selROI = None  # selected ROI index or None
        node.showStdDevs = False # show stddevs on canvas

    def perform(self, node):
        img = node.getInput(0, conntypes.IMG)
        # the perform for this node mainly draws ROIs once they are generated. The PCT outline is drawn
        # in the canvas draw hook.
        if img is not None:
            node.previewRadius = getRadiusFromSlider(node.brushSize, img.w, img.h, scale=BRUSHSCALE)
            img.setMapping(node.mapping)

            for r in node.rois:  # we need to tell the ROI how big the contained image is
                if r is not None:
                    r.setImageSize(img.w, img.h)

            # get the RGB image we are going to draw the ROIs onto. Will only draw if there are ROIs!

            node.rgbImage = img.rgbImage()
            if node.drawMode != 'None':
                for i, r in enumerate(node.rois):
                    if r is not None:
                        p = pct.patches[i]
                        r.setDrawProps(True, p.col, 0, 1,  # font size zero
                                       True)
                        r.drawEdge = (node.drawMode == 'Edge')
                        r.drawBox = i == (node.selROI)
                        r.draw(node.rgbImage.img)
        node.img = img

    def uichange(self, n):
        self.perform(n)

    def stddev(self, node, idx):
        """get stats for a given patch (by index). This is the mean of the stddevs across all channels;
        otherwise we'd get very high stddev for (say) blue and low for black and white! Return value may be masked
        if there are no unmasked pixels."""
        if not node.rois or node.rois[idx] is None or node.img is None:
            return None
        # get subimage
        subimg = node.img.subimage(roi=node.rois[idx])
        # get masked ROI image
        masked = subimg.masked()
        stddev = np.mean(masked.std(axis=(0,1)))
        return stddev

    def generateROIs(self, n):
        """Generate the regions of interest for the colour patches. These are
        stored in a list in the same order as in pct.patches."""

        # We need to get from PCT space to image space
        pts1 = np.float32(pct.screws)
        pts2 = np.float32(n.pctPoints)
        # get affine transform
        M = cv.getAffineTransform(pts1, pts2)
        #  max scale factor
        maxScale = np.max(M[:2,:2])
        print("scale from PCT coords to screen coords:",maxScale)

        n.rois = []
        # ROIs must be indexed the same as patches in pct.patches
        for p in pct.patches:
            # get patch centre, convert to image space, get xy coords.
            pp = np.float32([[[p.x, p.y]]])
            x, y = cv.transform(pp, M).ravel().tolist()
            roi = createPatchROI(n, x, y, p.r * maxScale)
            n.rois.append(roi)


def transformPoints(points, matrix):
    """Use cv.transform to transform a list of points [[x,y],[x,y]...] with a 2x3 affine transform
    as generated by cv.affineTransform etc."""
    # first, put the data into a numpy array with a format cv.transform likes
    # with a pointless extra dimension
    points = np.float32(points).reshape(-1, 1, 2)
    # then transform and reshape losing that dimension
    points = cv.transform(points, matrix).reshape(-1, 2)
    return points


def drawCircle(cx, cy, r, matrix, painter, canvas):
    points = [
        [cx + r * np.sin(theta), cy + r * np.cos(theta)] for theta in np.arange(0, 2 * np.pi, np.pi / 32)
    ]

    points = transformPoints(points, matrix)
    points = [canvas.getCanvasCoords(*p) for p in points]
    painter.drawPolygon(QPolygon([QPoint(*p) for p in points]))


class TabPCT(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabpctcalib.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook = self
        self.w.canvas.mouseHook = self
        self.w.brushSize.valueChanged.connect(self.brushSizeChanged)
        self.w.rotateButton.clicked.connect(self.rotatePressed)
        self.w.clearButton.clicked.connect(self.clearPressed)
        self.w.genButton.clicked.connect(self.genPressed)
        self.w.drawMode.currentIndexChanged.connect(self.drawModeChanged)
        self.w.stddevsBox.stateChanged.connect(self.stddevsBoxChanged)
        self.w.canvas.canvas.setMouseTracking(True)
        self.mousePos = None
        self.mouseDown = False
        # sync tab with node
        self.nodeChanged()

    def drawModeChanged(self, val):
        self.node.drawMode = self.w.drawMode.currentText()
        self.changed()

    def stddevsBoxChanged(self, val):
        self.node.showStdDevs = (val != 0)
        self.changed()

    def brushSizeChanged(self, val):
        self.node.brushSize = val
        self.changed()

    def clearPressed(self):
        if QMessageBox.question(self.parent(), "Clear points", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.mark()
            self.node.pctPoints.clear()
            self.node.rois = []
            self.changed()

    def rotatePressed(self):
        if len(self.node.pctPoints) == 3:
            self.mark()
            p = self.node.pctPoints
            p = p[1:] + p[:1]  # could do this with a deque, but they can't serialise.
            self.node.pctPoints = p
            self.changed()

    def genPressed(self):
        if len(self.node.pctPoints) == 3:
            self.mark()
            self.node.type.generateROIs(self.node)
            self.node.pctPoints.clear()
            self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)

        # some buttons are disabled in some modes
        if not self.node.rois:  # empty ROI list
            rotateEnabled = len(self.node.pctPoints) == 3
            genEnabled = len(self.node.pctPoints) == 3
            clearEnabled = len(self.node.pctPoints) > 0
        else:
            rotateEnabled = False
            genEnabled = False
            clearEnabled = True
        self.w.clearButton.setEnabled(clearEnabled)
        self.w.genButton.setEnabled(genEnabled)
        self.w.rotateButton.setEnabled(rotateEnabled)
        self.w.drawMode.setCurrentIndex(self.w.drawMode.findText(self.node.drawMode))

        if self.node.img is not None:
            # We're displaying a "premapped" image : this node's perform code is
            # responsible for doing the RGB mapping, unlike most other nodes where it's
            # done in the canvas for display purposes only
            self.w.canvas.display(self.node.rgbImage, self.node.img, self.node)
        self.w.brushSize.setValue(self.node.brushSize)
        self.w.stddevsBox.setCheckState(2 if self.node.showStdDevs else 0)
        self.w.roiHelpLabel.setEnabled(len(self.node.rois) > 0)

    def drawStats(self, p: QPainter):
        if self.node.rois:
            FONTSIZE = 20
            prevfont = p.font()
            p.setPen(Qt.black)
            p.setBrush(Qt.black)
            p.drawRect(0, 0, 300, 180)
            font = QFont("Consolas")
            font.setPixelSize(FONTSIZE)
            p.setFont(font)
            p.setPen(Qt.white)
            for idx, roi in enumerate(self.node.rois):
                patch = pct.patches[idx]
                if roi is not None:
                    std = self.node.type.stddev(self.node, idx)
                    if std == masked:
                        s = "{}\t\tno data".format(patch.name, std)
                    else:
                        s = "{}\t\t{:.3f}".format(patch.name, std)
                else:
                    s = "{}\t\t---".format(patch.name)
                p.drawText(0, (idx + 1) * FONTSIZE, s)

            p.setFont(prevfont)

    # extra drawing operations
    def canvasPaintHook(self, p: QPainter):
        # unlike in the ROIs, we are drawing onto the canvas widget
        # rather than drawing on the image in perform(). Note the use of
        # getCanvasCoords to get from image to widget coords (dealing with
        # zoom and pan).
        c = self.w.canvas
        n = self.node
        if not n.rois:  # if there are ROIs
            p.setPen(QColor(255, 255, 255))
            for idx, pt in enumerate(n.pctPoints):
                if idx == n.selPoint:
                    p.setPen(QColor(255, 0, 0))
                else:
                    p.setPen(QColor(255, 255, 255))
                x, y = c.getCanvasCoords(*pt)
                p.drawEllipse(x - 5, y - 5, 10, 10)

            if len(n.pctPoints) == 3:
                # we have enough points to perform the mapping!
                # we want to go from PCT into image space
                pts1 = np.float32(pct.screws)
                pts2 = np.float32(n.pctPoints)
                # get affine transform
                M = cv.getAffineTransform(pts1, pts2)

                # draw the surrounding rect by passing in points in PCT-space
                # and converting to image space

                points = [
                    [0, 0],  # note the extra level!
                    [pct.width, 0],
                    [pct.width, pct.height],
                    [0, pct.height]
                ]

                # transform points with affine transform
                points = transformPoints(points, M)
                # also impose the image->canvas transform
                points = [c.getCanvasCoords(*p) for p in points]
                # build a poly, and draw
                p.setPen(QColor(255, 255, 255))
                p.drawPolygon(QPolygon([QPoint(*p) for p in points]))

                # now draw the patches
                for patch in pct.patches:
                    drawCircle(patch.x, patch.y, patch.r, M, p, c)
        else:
            # we are editing ROIS; draw the preview circle
            if self.mousePos is not None and n.previewRadius is not None and n.selROI is not None:
                # draw brush preview
                p.setPen(Qt.white)
                r = n.previewRadius / (self.w.canvas.canvas.getScale())
                p.drawEllipse(self.mousePos, r, r)
            if n.showStdDevs:
                self.drawStats(p)


    def canvasMouseMoveEvent(self, x, y, e):
        self.mousePos = e.pos()
        n = self.node
        if self.mouseDown:
            if not n.rois:
                if n.selPoint >= 0:
                    n.pctPoints[n.selPoint] = (x, y)
                    self.changed()
            else:
                if n.selROI is not None:
                    self.doSet(x, y, e)
                    self.changed()
        self.w.canvas.update()

    def selectROI(self, x, y):
        n = self.node
        mindist = None
        for idx, roi in enumerate(n.rois):
            px, py = roi.centroid()
            dx = px - x
            dy = py - y
            dsq = dx * dx + dy * dy
            if dsq < 70 and (mindist is None or dsq < mindist):
                n.selROI = idx
                mindist = dsq

    def canvasMousePressEvent(self, x, y, e):
        self.mark()
        self.mouseDown = True
        n = self.node
        changed = False
        if not n.rois:
            # first look for an existing point
            mindist = None
            n.selPoint = -1
            for idx, pt in enumerate(n.pctPoints):
                px, py = pt
                dx = px - x
                dy = py - y
                dsq = dx * dx + dy * dy
                if dsq < 70 and (mindist is None or dsq < mindist):
                    n.selPoint = idx
                    mindist = dsq
                    changed = True
            # if no selected point, and we can do it, create a new point
            if mindist is None and len(n.pctPoints) < 3:
                n.pctPoints.append((x, y))
                changed = True
        else:
            if e.modifiers() & Qt.ControlModifier:
                # select an ROI
                self.selectROI(x, y)
                changed = True
            else:
                if n.selROI is not None:
                    self.doSet(x, y, e)
                    changed = True
        if changed:
            self.changed()
            self.w.canvas.update()

    def doSet(self, x, y, e):
        n = self.node
        if e.modifiers() & Qt.ShiftModifier:
            n.rois[n.selROI].setCircle(x, y, n.brushSize*BRUSHSCALE, True)
        else:
            n.rois[n.selROI].setCircle(x, y, n.brushSize*BRUSHSCALE, False)

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
