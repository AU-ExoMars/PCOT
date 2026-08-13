import numpy as np
from numpy.ma import masked

from pcot.calib.target import CircularPatch, RectPatch
from pcot.datum import Datum
import cv2 as cv

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QPainter, QPolygon, QFont
from PySide6.QtWidgets import QMessageBox
import pcot.calib.pct
import pcot.calib.colorchecker_classic
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.rois import getRadiusFromSlider, ROIPainted
from pcot.utils.deb import Timer
from pcot.utils.flood import MeanFloodFiller, FloodFillParams
from pcot.xform import xformtype, XFormType, XFormException
from pcot.xforms.tabgeneric import TabGeneric

# scale of editing brush
BRUSHSCALE = 0.1


def patchBoundRadius(p):
    """Get an equivalent radius in mm for a patch, used to bound the flood fill area and
    as the fallback circle size if the flood fill fails."""
    if isinstance(p, CircularPatch):
        return p.r
    elif isinstance(p, RectPatch):
        return min(p.w, p.h) / 2
    else:
        raise XFormException('DATA', f"unsupported patch type {p.__class__.__name__}")


def patchOutlinePoints(p, scale=1.0):
    """List of (x,y) points in PCT space tracing the patch's outline, scaled about its centre.
    Used both to preview a patch's shape and (in 'Shape' ROI generation mode) to build its ROI,
    so the two are always identical."""
    if isinstance(p, CircularPatch):
        r = p.r * scale
        return [
            [p.x + r * np.sin(theta), p.y + r * np.cos(theta)] for theta in np.arange(0, 2 * np.pi, np.pi / 32)
        ]
    elif isinstance(p, RectPatch):
        w, h = p.w * scale, p.h * scale
        return [
            [p.x - w / 2, p.y - h / 2],
            [p.x + w / 2, p.y - h / 2],
            [p.x + w / 2, p.y + h / 2],
            [p.x - w / 2, p.y + h / 2],
        ]
    else:
        raise XFormException('DATA', f"unsupported patch type {p.__class__.__name__}")


def createPatchROI(img, x, y, radius, tolerance):
    """Create a ROIPainted which encompasses the coords x,y, using MeanFloodFiller: each
    candidate pixel is compared against a running mean of the fill so far, rather than a fixed
    seed value, so the fill tolerates the smooth lighting gradients/vignetting real patches have.
    'tolerance' is a direct, linear intensity difference (squared internally, since
    MeanFloodFiller's own threshold is a squared distance - this keeps the user-facing number
    directly interpretable). The patch's radius in mm caps how many pixels the fill is allowed to
    grow to - a fill that would otherwise bleed into a neighbouring patch simply stops growing at
    that size, it isn't discarded. We only fall back to a small circle around the point if nothing
    at all could be filled. This is destructive - it works on a copy of the image."""

    maxPix = radius ** 2 * 4
    ff = MeanFloodFiller(img, FloodFillParams(0, maxPix, threshold=tolerance ** 2))
    roi = ff.fillToPaintedRegion(int(x), int(y))
    if roi is None:
        roi = ROIPainted()
        roi.setContainingImageDimensions(img.w, img.h)
        roi.setCircle(x, y, radius / 4)
        roi.cropDownWithDraw()
    return roi


def createShapeROI(img, points):
    """Create a ROIPainted by filling a polygon (image-space points) directly, rather than
    flood-filling. Used for 'Shape' ROI generation mode, where the ROI is exactly the patch's
    perspective-projected outline (see patchOutlinePoints) instead of an organic flood-filled blob."""
    roi = ROIPainted()
    roi.setContainingImageDimensions(img.w, img.h)
    pts = np.array(points, np.int32).reshape((-1, 1, 2))
    roi.cropDownWithDraw(draw=lambda fullsize: cv.fillPoly(fullsize, [pts], 255))
    return roi


class CalibrationTargetBase(XFormType):
    """Locates the PCT by hand and creates ROIs"""

    def __init__(self, name, group, ver, target):
        super().__init__(name, group, ver)
        self.addInputConnector("img", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.params = TaggedDictType()  # no parameters; it's pointless because the ROIs are painted.
        self.autoserialise = ('brushSize', 'pctPoints', 'drawMode', ('roiScale', 1.0),
                              ('roiGenMode', 'Shape'),
                              ('roiLabelSize', 4),
                              ('floodTolerance', 0.05))
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
        node.roiScale = 1.0
        node.roiGenMode = 'Shape'
        node.floodTolerance = 0.05
        node.drawMode = 'Fill'
        # (x,y) tuples for screen positions of screws; a deque so we can rotate
        node.pctPoints = []
        node.selPoint = -1  # selected point to move
        node.selPoint = -1  # selected point to move
        node.rois = []  # list of ROIs (ROIPainted); if none then we're editing points.
        node.selROI = None  # selected ROI index or None
        node.showStdDevs = False  # show stddevs on canvas
        node.roiLabelSize = 4  # roi label size 0-20

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

                        r.fontsize = node.roiLabelSize
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
        stored in a list in the same order as in pct.patches. Depending on n.roiGenMode,
        either flood-fills out from each patch centre, or fills the patch's perspective-
        projected outline directly (necessary since that outline is generally not a
        rectangle or circle once the perspective distortion is applied)."""

        # We need to get from PCT space to image space
        pts1 = np.float32(self.target.regpoints)
        pts2 = np.float32(n.pctPoints)
        # get affine transform
        if len(n.pctPoints) == 4:
            M = cv.getPerspectiveTransform(pts1, pts2)
        else:
            M = cv.getAffineTransform(pts1, pts2)
        #  max scale factor
        maxScale = np.max(M[:2, :2])

        n.rois = []
        # ROIs must be indexed the same as patches in pct.patches

        timer = Timer("flood")
        tmpimg = n.img.copy()  # temp copy to work on
        for p in self.target.patches:
            if n.roiGenMode == 'Shape':
                points = transformPoints(patchOutlinePoints(p, n.roiScale), M)
                roi = createShapeROI(tmpimg, points)
            else:
                (x, y), = transformPoints([[p.x, p.y]], M)
                roi = createPatchROI(tmpimg, x, y, patchBoundRadius(p) * maxScale, n.floodTolerance)
            n.rois.append(roi)
        timer.mark("done")


def transformPoints(points, matrix):
    """Transform the points - the matrix is either 2x3 or 3x3. These methods expect and produce point
    arrays in the form [n,1,2] and we are working in [n,2] so some reshaping is necessary"""
    points = np.float32(points).reshape(-1, 1, 2)
    if matrix.shape == (3,3):
        points = cv.perspectiveTransform(points,matrix)
    else:
        points = cv.transform(points, matrix)
    return points.reshape(-1, 2)


def drawPatchOutline(patch, scale, matrix, painter, canvas):
    """Draw a patch's projected outline (see patchOutlinePoints) onto the canvas."""
    points = transformPoints(patchOutlinePoints(patch, scale), matrix)
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
        self.w.stddevsBox.checkStateChanged.connect(self.stddevsBoxChanged)
        self.w.roiScale.valueChanged.connect(self.roiScaleChanged)
        self.w.roiGenMode.currentIndexChanged.connect(self.roiGenModeChanged)
        self.w.floodTolerance.valueChanged.connect(self.floodToleranceChanged)
        self.w.roiLabelSize.valueChanged.connect(self.roiLabelSizeChanged)
        self.w.canvas.canvas.setMouseTracking(True)
        self.target = node.type.target
        self.mousePos = None
        self.mouseDown = False
        # sync tab with node
        self.nodeChanged()

    def roiLabelSizeChanged(self, val):
        self.node.roiLabelSize = val
        self.changed()

    def roiScaleChanged(self, val):
        self.node.roiScale = val
        self.changed()

    def roiGenModeChanged(self, val):
        self.node.roiGenMode = self.w.roiGenMode.currentText()
        self.changed()

    def floodToleranceChanged(self, val):
        self.node.floodTolerance = val
        self.changed()

    def drawModeChanged(self, val):
        self.node.drawMode = self.w.drawMode.currentText()
        self.changed()

    def stddevsBoxChanged(self, val):
        self.node.showStdDevs = (val == Qt.CheckState.Checked)
        self.changed()

    def brushSizeChanged(self, val):
        self.node.brushSize = val
        self.changed()

    def clearPressed(self):
        if QMessageBox.question(self.window, "Clear points", "Are you sure?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.mark()
            # if we have ROIs, we just clear them. On the second press - no ROIs, but points, we clear points.
            if self.node.rois:
                self.node.rois = []
            elif len(self.node.pctPoints) > 0:
                self.node.pctPoints.clear()
            self.changed()

    def rotatePressed(self):
        if len(self.node.pctPoints) == len(self.target.regpoints):
            self.mark()
            p = self.node.pctPoints
            p = p[1:] + p[:1]  # could do this with a deque, but they can't serialise.
            self.node.pctPoints = p
            self.changed()

    def genPressed(self):
        if len(self.node.pctPoints) == len(self.target.regpoints):
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
        self.w.roiScale.setValue(self.node.roiScale)
        self.w.genButton.setEnabled(readyToGen)
        self.w.rotateButton.setEnabled(readyToGen)
        self.w.drawMode.setCurrentIndex(self.w.drawMode.findText(self.node.drawMode))
        self.w.roiGenMode.setCurrentIndex(self.w.roiGenMode.findText(self.node.roiGenMode))
        self.w.floodTolerance.setValue(self.node.floodTolerance)
        # roiScale only affects Shape mode; floodTolerance only affects Flood Fill mode
        isShape = self.node.roiGenMode == 'Shape'
        self.w.roiScale.setEnabled(isShape)
        self.w.floodTolerance.setEnabled(not isShape)
        self.w.roiLabelSize.setValue(self.node.roiLabelSize)

        self.w.canvas.setNode(self.node)
        if self.node.img is not None:
            # We're displaying a "premapped" image : this node's perform code is
            # responsible for doing the RGB mapping, unlike most other nodes where it's
            # done in the canvas for display purposes only
            self.w.canvas.display(self.node.rgbImage, self.node.img, self.node)
        self.w.brushSize.setValue(self.node.brushSize)
        self.w.stddevsBox.setCheckState(Qt.CheckState.Checked if self.node.showStdDevs else Qt.CheckState.Unchecked)
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
            p.setPen(Qt.GlobalColor.black)
            p.setBrush(Qt.GlobalColor.black)
            p.drawRect(0, 0, 400, 20*len(self.node.rois)+40)
            font = QFont("Consolas")
            # fontsize = pixels2painter(FONTSIZE, p)
            fontsize = FONTSIZE
            font.setPixelSize(fontsize)
            p.setFont(font)
            p.setPen(Qt.GlobalColor.white)
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
            p.setBrush(Qt.BrushStyle.NoBrush)
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
                # get transform
                if len(n.pctPoints) == 4:
                    M = cv.getPerspectiveTransform(pts1, pts2)
                elif len(n.pctPoints) == 3:
                    M = cv.getAffineTransform(pts1, pts2)
                else:
                    raise XFormException('DATA', "unsupported number of points to generate transform")

                # draw the surrounding rect by passing in points in PCT-space
                # and converting to image space

                points = [
                    [0, 0],
                    [self.target.width, 0],
                    [self.target.width, self.target.height],
                    [0, self.target.height]
                ]

                # transform points with transform
                points = transformPoints(points, M)
                # also impose the image->canvas transform
                points = [c.getCanvasCoords(*p) for p in points]
                # build a poly, and draw
                p.setPen(QColor(255, 255, 255))
                p.drawPolygon(QPolygon([QPoint(*p) for p in points]))

                # now draw the patches, at the size they'll actually be generated at (roiScale
                # only applies in Shape mode - Flood Fill mode is governed by floodTolerance instead)
                scale = n.roiScale if n.roiGenMode == 'Shape' else 1.0
                for patch in self.target.patches:
                    drawPatchOutline(patch, scale, M, p, c)
        else:
            # we are editing ROIS; draw the preview circle
            if self.mousePos is not None and n.previewRadius is not None and n.selROI is not None:
                # draw brush preview
                p.setPen(Qt.GlobalColor.white)
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
            if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
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
        if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            n.rois[n.selROI].setCircle(x, y, n.brushSize * BRUSHSCALE, True)
        else:
            n.rois[n.selROI].setCircle(x, y, n.brushSize * BRUSHSCALE, False)

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False


# Shared explanation of the ROI-generation controls, appended to both XFormPCT's and
# XFormColorCheckerClassic's docstrings below so this doesn't have to be maintained twice.
# getHelpMarkdown's common-leading-whitespace strip (pcot.ui.help.md2html) can't be relied on here:
# a docstring's first line is always flush-left (it follows the opening triple-quote on the same
# source line) while later lines carry the class body's indentation, so the computed "common"
# indentation is always 0 and nothing actually gets stripped. That's harmless for a single paragraph
# (Markdown treats an indented continuation line as part of the same paragraph), but this block starts
# a new paragraph after a blank line, and 4+ spaces of indentation there would read as a code block -
# so every line here must start flush-left (0 or 2 spaces for list-item continuations only).
_ROI_CONTROLS_HELP = """

Once the control points are placed, **Generate ROIs** builds one ROI per patch.

* **ROI Generation Mode** - *Shape* (the default) fills each patch's outline exactly as projected
  by the perspective transform - reliable even for small or heavily-distorted targets. *Flood Fill*
  instead grows a region outward from each patch's centre, following similar-coloured pixels.
* **ROI scale** - only used in *Shape* mode. Scales the projected patch outline about its centre,
  shown live as a preview before you click Generate.
* **Flood Fill Tolerance** - only used in *Flood Fill* mode. The maximum brightness difference a
  pixel may have from the fill's running average and still be included; too low and the fill stops
  almost immediately, too high and it may bleed into neighbouring patches.
* **ROI Draw Mode** / **ROI Label Size** - how the generated ROIs are annotated on the canvas."""


@xformtype
class XFormPCT(CalibrationTargetBase):
    """Allows the user to locate the PANCAM Calibration Target in an image by specifying control points,
    move those control points, and generate ROIs for each patch."""
    def __init__(self):
        super().__init__("pct", "calibration", "0.0.0",
                         pcot.calib.pct.target)


XFormPCT._cls.__doc__ += _ROI_CONTROLS_HELP  # __doc__ lives on the wrapped class - @xformtype rebinds the name


@xformtype
class XFormColorCheckerClassic(CalibrationTargetBase):
    """Allows the user to locate a GretagMacbeth ColorChecker Classic in an image by specifying
    control points, move those control points, and generate ROIs for each patch."""
    def __init__(self):
        super().__init__("colorchecker", "calibration", "0.0.0",
                         pcot.calib.colorchecker_classic.target)


XFormColorCheckerClassic._cls.__doc__ += _ROI_CONTROLS_HELP


@xformtype
class XFormCalibrate(XFormType):
    """
    Perform calibration of an image given the coefficients m,c from a reflectance
    node (or possibly elsewhere). These are vectors of gradient and intercept for
    each channel.
    """
    def __init__(self):
        super().__init__("calibrate", "calibration","0.0.0")
        self.addInputConnector("img", Datum.IMG)
        self.addInputConnector("m", Datum.NUMBER)
        self.addInputConnector("c", Datum.NUMBER)
        self.addOutputConnector("", Datum.IMG)

    def perform(self, node):
        img = node.getInput(0, Datum.IMG, return_datum=True)
        m = node.getInput(1, Datum.NUMBER, return_datum=True)
        c = node.getInput(2, Datum.NUMBER, return_datum=True)
        img = (img - c)/m
        node.setOutput(0, img)

    def init(self,node):
        pass

    def createTab(self, xform, window):
        return TabGeneric(xform, window)