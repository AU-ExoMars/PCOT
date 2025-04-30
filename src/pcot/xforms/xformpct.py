import numpy as np
from numpy.ma import masked

from pcot.calib.target import CircularPatch
from pcot.datum import Datum
import cv2 as cv

from PySide2.QtCore import Qt, QPoint
from PySide2.QtGui import QColor, QPainter, QPolygon, QFont
from PySide2.QtWidgets import QMessageBox
import pcot.calib.pct
import pcot.calib.colorchecker_classic
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.rois import getRadiusFromSlider, ROIPainted
from pcot.utils.annotations import pixels2painter
from pcot.utils.deb import Timer
from pcot.utils.flood import MeanFloodFiller, FloodFillParams
from pcot.xform import xformtype, XFormType, XFormException

# scale of editing brush
BRUSHSCALE = 0.1


def createPatchROI(img, x, y, radius):
    """Create a ROIPainted which encompasses the coords x,y. The patch has
    a given radius in mm, which we use to determine the min and max number
    of pixels acceptable. This works using a floodfill on the image, so it is
    *destructive*"""

    # first step - create a bool mask the same size as the image, all zeroes.

    # second step - perform a flood fill of this mask, using the image itself
    # as a reference. Fill should stop when the point about to be filled is
    # very far from the mean of the points so far.

    # get minimum and maximum pixel sizes (empirically determined from radius of patch)
    maxPix = radius ** 2 * 4
    minPix = 0  # probably best to not have a min pixel count
    ff = MeanFloodFiller(img, FloodFillParams(minPix, maxPix, threshold=0.005))

    # perform a flood fill and get a region out. This may return None if the
    # number of pixels is too low or too high. If so, we just fill a small region around
    # the point.
    roi = ff.fillToPaintedRegion(int(x), int(y))
    if roi is None:
        roi = ROIPainted()
        roi.setContainingImageDimensions(img.w, img.h)
        roi.setCircle(x, y, radius / 4)
        roi.cropDownWithDraw()
    return roi


class CalibrationTargetBase(XFormType):
    """Locates the PCT by hand and creates ROIs"""

    def __init__(self, name, group, ver, target):
        super().__init__(name, group, ver)
        self.addInputConnector("img", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.params = TaggedDictType()  # no parameters; it's pointless because the ROIs are painted.
        self.autoserialise = ('brushSize', 'pctPoints', 'drawMode', ('radiusScale', 1.0))
        self.target = target

    def createTab(self, n, w):
        return TabPCT(n, w)

    def serialise(self, n):
        return {'rois': [None if roi is None else roi.serialise() for roi in n.rois]}

    def deserialise(self, n, d):
        n.rois = []
        if 'rois' in d:
            for ent in d['rois']:
                r = ROIPainted()
                if ent is not None:
                    r.deserialise(ent)
                n.rois.append(r)

    def init(self, node):
        node.img = None
        node.data = None
        node.rgbImage = None
        node.previewRadius = None  # previewing needs the image, but that's awkward - so we stash this data in perform()
        node.brushSize = 10
        node.radiusScale = 1.0
        node.drawMode = 'Fill'
        # (x,y) tuples for screen positions of screws; a deque so we can rotate
        node.pctPoints = []
        node.selPoint = -1  # selected point to move
        node.selPoint = -1  # selected point to move
        node.rois = []  # list of ROIs (ROIPainted); if none then we're editing points.
        node.selROI = None  # selected ROI index or None
        node.showStdDevs = False  # show stddevs on canvas

    def perform(self, node):
        img_in = node.getInput(0, Datum.IMG)
        # the perform for this node mainly draws ROIs once they are generated. The PCT outline is drawn
        # in the canvas draw hook.
        if img_in is not None:
            img = img_in.shallowCopy()  # Issue 56!
            node.previewRadius = getRadiusFromSlider(node.brushSize, img.w, img.h, scale=BRUSHSCALE)
            img.setMapping(node.mapping)

            for r in node.rois:  # we need to tell the ROI how big the contained image is
                if r is not None:
                    r.setContainingImageDimensions(img.w, img.h)

            # get the RGB image we are going to draw the ROIs onto. Will only draw if there are ROIs!
            # make sure we respect the canvas mapping, which is written into the node.

            # This will "premap" the image - it will use the image's map to generate RGB. We need to
            # make sure this map is set by the node.

            node.rgbImage = img.rgbImage()  # this is the image we draw the PREVIEW rois into, I think.

            # add the annotations to it.
            if node.drawMode != 'None':
                for i, r in enumerate(node.rois):
                    if r is not None:
                        p = self.target.patches[i]
                        r.label = p.name
                        r.labeltop = True
                        r.colour = p.col
                        r.fontsize = 8
                        r.thickness = 0
                        r.drawbg = True
                        r.drawEdge = (node.drawMode == 'Edge')
                        r.drawBox = (i == node.selROI)
                        node.rgbImage.annotations.append(r)

            img.rois = node.rois
            node.img = img
            # also add the ROIs to that
            node.setOutput(0, Datum(Datum.IMG, img))
        else:
            node.setOutput(0, Datum.null)

    def clearData(self, xform):
        xform.img = None

    def uichange(self, n):
        n.timesPerformed += 1
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
        stddev = np.mean(masked.std(axis=(0, 1)))
        return stddev

    def generateROIs(self, n):
        """Generate the regions of interest for the colour patches. These are
        stored in a list in the same order as in pct.patches."""

        # We need to get from PCT space to image space
        pts1 = np.float32(self.target.regpoints)
        pts2 = np.float32(n.pctPoints)
        # get affine transform
        M = cv.getAffineTransform(pts1, pts2)
        #  max scale factor
        maxScale = np.max(M[:2, :2])

        n.rois = []
        # ROIs must be indexed the same as patches in pct.patches

        timer = Timer("flood")
        tmpimg = n.img.copy()  # temp copy to work on
        for p in self.target.patches:
            # get patch centre, convert to image space, get xy coords.
            pp = np.float32([[[p.x, p.y]]])
            x, y = cv.transform(pp, M).ravel().tolist()
            roi = createPatchROI(tmpimg, x, y, p.r * maxScale * n.radiusScale)
            n.rois.append(roi)
        timer.mark("done")


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
        self.w.radiusScale.valueChanged.connect(self.radiusScaleChanged)
        self.w.canvas.canvas.setMouseTracking(True)
        self.target = node.type.target
        self.mousePos = None
        self.mouseDown = False
        # sync tab with node
        self.nodeChanged()

    def radiusScaleChanged(self, val):
        self.node.radiusScale = val
        self.changed()

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
        if QMessageBox.question(self.window, "Clear points", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.mark()
            # if we have ROIs, we just clear them. On the second press - no ROIs, but points, we clear points.
            if self.node.rois:
                self.node.rois = []
            elif len(self.node.pctPoints) > 0:
                self.node.pctPoints.clear()
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
            self.changed()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # some buttons are disabled in some modes
        if not self.node.rois:  # empty ROI list
            readyToGen = len(self.node.pctPoints) == len(self.target.regpoints)
            clearEnabled = len(self.node.pctPoints) > 0
        else:
            readyToGen = False
            clearEnabled = True
        self.w.clearButton.setEnabled(clearEnabled)
        self.w.radiusScale.setValue(self.node.radiusScale)
        self.w.genButton.setEnabled(readyToGen)
        self.w.rotateButton.setEnabled(readyToGen)
        self.w.drawMode.setCurrentIndex(self.w.drawMode.findText(self.node.drawMode))

        self.w.canvas.setNode(self.node)
        if self.node.img is not None:
            # We're displaying a "premapped" image : this node's perform code is
            # responsible for doing the RGB mapping, unlike most other nodes where it's
            # done in the canvas for display purposes only
            self.w.canvas.display(self.node.rgbImage, self.node.img, self.node)
        self.w.brushSize.setValue(self.node.brushSize)
        self.w.stddevsBox.setCheckState(Qt.Checked if self.node.showStdDevs else Qt.Unchecked)
        if len(self.node.rois) < 1:
            if readyToGen:
                t = self.target.instructions2
            else:
                t = self.target.instructions1
        else:
            t = "Ctrl-Click to select an ROI, then Click to paint extra pixels or Shift-Click " \
                "to remove them"
        self.w.roiHelpLabel.setText(t)

    def drawStats(self, p: QPainter):
        if self.node.rois:
            FONTSIZE = 20
            prevfont = p.font()
            p.setPen(Qt.black)
            p.setBrush(Qt.black)
            p.drawRect(0, 0, 400, 20*len(self.node.rois)+40)
            font = QFont("Consolas")
            fontsize = pixels2painter(FONTSIZE, p)
            font.setPixelSize(fontsize)
            p.setFont(font)
            p.setPen(Qt.white)
            for idx, roi in enumerate(self.node.rois):
                patch = self.target.patches[idx]
                if roi is not None:
                    std = self.node.type.stddev(self.node, idx)
                    name = f"{patch.name}/{patch.desc}"
                    if std == masked:
                        s = f"{name:20}\t\tno data"
                    else:
                        s = f"{name:20}\t\t{std:.3f}"
                else:
                    s = "{}\t\t---".format(patch.name)
                p.drawText(0, (idx + 1) * fontsize, s)

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
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(255, 255, 255))
            for idx, pt in enumerate(n.pctPoints):
                if idx == n.selPoint:
                    p.setPen(QColor(255, 0, 0))
                else:
                    p.setPen(QColor(255, 255, 255))
                x, y = c.getCanvasCoords(*pt)
                p.drawEllipse(x - 5, y - 5, 10, 10)

            if len(n.pctPoints) == len(self.target.regpoints):
                # we have enough points to perform the mapping!
                # we want to go from PCT into image space
                pts1 = np.float32(self.target.regpoints)
                pts2 = np.float32(n.pctPoints)
                # get affine transform
                M = cv.getAffineTransform(pts1, pts2)

                # draw the surrounding rect by passing in points in PCT-space
                # and converting to image space

                points = [
                    [0, 0],
                    [self.target.width, 0],
                    [self.target.width, self.target.height],
                    [0, self.target.height]
                ]

                # transform points with affine transform
                points = transformPoints(points, M)
                # also impose the image->canvas transform
                points = [c.getCanvasCoords(*p) for p in points]
                # build a poly, and draw
                p.setPen(QColor(255, 255, 255))
                p.drawPolygon(QPolygon([QPoint(*p) for p in points]))

                # now draw the patches
                for patch in self.target.patches:
                    if isinstance(patch, CircularPatch):
                        drawCircle(patch.x, patch.y, patch.r, M, p, c)
                    else:
                        raise XFormException('DATA', f"unsupported patch type {patch.__class__.__name__}")
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
                    # dragging a point; this is just a UI change
                    n.pctPoints[n.selPoint] = (x, y)
                    self.changed(uiOnly=True)
            else:
                if n.selROI is not None:
                    # actually
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
            if mindist is None and len(n.pctPoints) < len(self.target.regpoints):
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
            n.rois[n.selROI].setCircle(x, y, n.brushSize * BRUSHSCALE, True)
        else:
            n.rois[n.selROI].setCircle(x, y, n.brushSize * BRUSHSCALE, False)

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False


@xformtype
class XFormPCT(CalibrationTargetBase):
    """Allows the user to locate the PANCAM Calibration Target in an image by specifying control points,
    move those control points, and generate ROIs for each patch by floodfill."""
    def __init__(self):
        super().__init__("pct", "calibration", "0.0.0",
                         pcot.calib.pct.target)

@xformtype
class XFormColorCheckerClassic(CalibrationTargetBase):
    """Allows the user to locate a GretagMacbeth ColorChecker Classic in an image by specifying
    control points, move those control points, and generate ROIs for each patch by floodfill."""
    def __init__(self):
        super().__init__("colorchecker", "calibration", "0.0.0",
                         pcot.calib.colorchecker_classic.target)
