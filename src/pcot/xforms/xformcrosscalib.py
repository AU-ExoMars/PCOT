import logging

import numpy as np
from PySide2.QtCore import Qt
from PySide2.QtGui import QKeyEvent, QPainter, QPen, QColor
from PySide2.QtWidgets import QMessageBox

from pcot import ui
from pcot.datum import Datum
import pcot.ui.tabs
from pcot.imagecube import ImageCube
from pcot.rois import ROICircle
from pcot.utils import text
from pcot.utils.annotations import Annotation, annotDrawText, annotFont, IndexedPointAnnotation
from pcot.xform import XFormType, xformtype, XFormException

logger = logging.Logger(__name__)

IMAGEMODE_SOURCE = 0
IMAGEMODE_DEST = 1
IMAGEMODE_RESULT = 2

IMAGEMODE_CT = 3


def findInList(lst, x, y):
    """Used to find a point in a list of points which is near a pair of coordinates.
    Returns the point index in the list. Crude, but doesn't need to be fast."""
    pt = None
    mindist = None

    for idx, ptcoords in enumerate(lst):
        px, py = ptcoords
        dx = px - x
        dy = py - y
        dsq = dx * dx + dy * dy
        if dsq < 100 and (mindist is None or dsq < mindist):
            pt = idx
            mindist = dsq
    return pt


class CrossCalibPointAnnotation(Annotation):
    def __init__(self, x, y, r, col):
        self.x = x
        self.y = y
        self.r = r
        self.col = col

    def annotate(self, p: QPainter, img, alpha):
        p.setBrush(Qt.NoBrush)
        col = QColor(Qt.yellow)
        col.setAlpha(alpha*255)
        pen = QPen(col)
        pen.setWidth(0)
        p.setPen(pen)

        p.drawEllipse(self.x - self.r, self.y - self.r, self.r*2, self.r*2)


@xformtype
class XFormCrossCalib(XFormType):
    """
    "Cross-calibrate" two images: given points S in a source image and corresponding points D in a
    destination image, find a vector of factors v for the bands such that S=vD, and transform S accordingly.
    Essentially, and crudely speaking, make the colours in S match those in D by sampling the same points in each.
    Bad pixels in the parent image will be ignored for getting the colours, and the new image will have the
    DQ bits from S.

    Uncertainty is not propagated through this node.

    DQ is propagated from the source image.
    """

    def __init__(self):
        super().__init__("crosscalib", "processing", "0.0.0")
        self.addInputConnector("source", Datum.IMG)
        self.addInputConnector("dest", Datum.IMG)
        self.addOutputConnector("out", Datum.IMG)
        self.autoserialise = ('showSrc', 'showDest', 'src', 'dest', ('r', 10))

    def init(self, node):
        node.img = None
        node.imagemode = IMAGEMODE_SOURCE
        node.showSrc = True
        node.showDest = True
        node.canvimg = None

        # source and destination points - there is a 1:1 mapping between the two
        node.src = []  # ditto
        node.dest = []  # list of (x,y) points
        # index of selected points
        node.selIdx = None
        # is the selected point (if any) in the dest list (or the source list)?
        node.selIsDest = False

        # default size of each 'point'
        node.r = 10

    def uichange(self, node):
        node.timesPerformed += 1
        self.perform(node, False)

    def perform(self, node, doApply=True):
        """Perform node. When called from uichange(), doApply will be False. Normally it's true."""
        sourceImg = node.getInput(0, Datum.IMG)
        destImg = node.getInput(1, Datum.IMG)

        if sourceImg is None or destImg is None:
            node.img = None  # output image (i.e. warped)
        else:
            if doApply:
                # actually do the work.
                outimg = self.apply(node, sourceImg, destImg)
                if outimg is not None:
                    node.img = ImageCube(outimg, sourceImg.mapping, sourceImg.sources, dq=sourceImg.dq)

            # which image are we viewing
            if node.imagemode == IMAGEMODE_DEST:
                img = destImg
            elif node.imagemode == IMAGEMODE_SOURCE:
                img = sourceImg
            elif node.img is not None:
                img = node.img
            else:
                img = None

            if img is not None:
                node.canvimg = img.copy()
                # add annotations to the image
                if node.showSrc:
                    issel = node.selIdx if not node.selIsDest else None
                    for i, (x, y) in enumerate(node.src):
                        node.canvimg.annotations.append(IndexedPointAnnotation(i, x, y, issel, Qt.yellow,
                                                                               radius=node.r))
                if node.showDest:
                    issel = node.selIdx if node.selIsDest else None
                    for i, (x, y) in enumerate(node.dest):
                        node.canvimg.annotations.append(IndexedPointAnnotation(i, x, y, issel, Qt.cyan,
                                                                               radius=node.r))
            else:
                node.canvimg = None

        node.setOutput(0, Datum(Datum.IMG, node.img))

    @staticmethod
    def delSelPoint(n):
        if n.selIdx is not None:
            if n.showSrc and not n.selIsDest:
                del n.src[n.selIdx]
                n.selIdx = None
            elif n.showDest and n.selIsDest:
                del n.dest[n.selIdx]
                n.selIdx = None

    @staticmethod
    def moveSelPoint(n, x, y):
        if n.selIdx is not None:
            if n.showSrc and not n.selIsDest:
                n.src[n.selIdx] = (x, y)
                return True
            elif n.showDest and n.selIsDest:
                n.dest[n.selIdx] = (x, y)
                return True
        return False

    @staticmethod
    def addPoint(n, x, y, dest):
        lst = n.dest if dest else n.src
        lst.append((x, y))

    @staticmethod
    def selPoint(n, x, y):
        if n.showSrc:
            pt = findInList(n.src, x, y)
            if pt is not None:
                n.selIdx = pt
                n.selIsDest = False
        if pt is None and n.showDest:
            pt = findInList(n.dest, x, y)
            if pt is not None:
                n.selIdx = pt
                n.selIsDest = True

    @staticmethod
    def apply(n, srcImg, destImg):
        # errors here must not be thrown, we need later stuff to run.
        if len(n.src) != len(n.dest):
            n.setError(XFormException('DATA', "Number of source and dest points must be the same"))
            return None
        if srcImg.channels != destImg.channels:
            n.setError(XFormException('DATA', "Source and dest images must have same number of channels"))
            return None

        # for each point, calculate the mean of the surrounding area for src and dest for each channel

        factors = []
        for (sx, sy), (dx, dy) in zip(n.src, n.dest):
            s = srcImg.subimage(roi=ROICircle(sx, sy, n.r))
            d = destImg.subimage(roi=ROICircle(dx, dy, n.r))

            # each of these will be an array of means, one for each channel, ignoring bad pixels.

            ss = s.masked(True)
            smeans = s.masked(True).mean(axis=(0, 1))
            dmeans = d.masked(True).mean(axis=(0, 1))

            if np.ma.any(smeans.mask):   # if any member of the mask is True (i.e. masked)
                raise XFormException('DATA', "Some source channels are completely masked by bad values - cannot calculate a mean")
            if np.ma.any(dmeans.mask):
                raise XFormException('DATA', "Some dest channels are completely masked by bad values - cannot calculate a mean")

            ui.log(str(smeans))

            # we add to the factors list the ratios of the means, band-wise, for each point. So
            # if the mean for band 0 in the source is s0 and the mean for band 0 in the dest is d0,
            # we add the array [d0/s0, d1/s1, d2/s2...]
            factors.append(dmeans / smeans)

        if len(factors) > 0:
            # so we then turn this into a points x band array..
            factors = np.array(factors)
            # and find the means across all the points.
            factors = np.mean(factors, axis=0)
            # we now have an array of ratios - one for each band - to convert source into dest!
            return (srcImg.img * factors).astype(np.float32)
        else:
            return srcImg.img

    def createTab(self, n, w):
        return TabCrossCalib(n, w)

    def clearData(self, n):
        n.canvimg = None


class TabCrossCalib(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabcrosscalib.ui')
        self.mouseDown = False
        self.w.canvas.keyHook = self
        self.w.canvas.mouseHook = self

        self.nodeChanged()  # doing this FIRST so signals don't go to slots during setup.

        self.w.radioSource.toggled.connect(self.radioViewToggled)
        self.w.radioDest.toggled.connect(self.radioViewToggled)
        self.w.radioResult.toggled.connect(self.radioViewToggled)

        self.w.checkBoxDest.toggled.connect(self.checkBoxDestToggled)
        self.w.checkBoxSrc.toggled.connect(self.checkBoxSrcToggled)

        self.w.clearButton.clicked.connect(self.clearClicked)

    def clearClicked(self):
        if QMessageBox.question(self.window, "Clear all points", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.mark()
            self.node.dest = []
            self.node.src = []
            self.node.selIdx = None
            self.changed()

    def radioViewToggled(self):
        self.mark()
        if self.w.radioSource.isChecked():
            self.node.imagemode = IMAGEMODE_SOURCE
        elif self.w.radioDest.isChecked():
            self.node.imagemode = IMAGEMODE_DEST
        elif self.w.radioResult.isChecked():
            self.node.imagemode = IMAGEMODE_RESULT
        self.changed(uiOnly=True)

    def checkBoxDestToggled(self):
        self.mark()
        self.node.showDest = self.w.checkBoxDest.isChecked()
        self.changed(uiOnly=True)

    def checkBoxSrcToggled(self):
        self.mark()
        self.node.showSrc = self.w.checkBoxSrc.isChecked()
        self.changed(uiOnly=True)

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        self.w.radioSource.setChecked(self.node.imagemode == IMAGEMODE_SOURCE)
        self.w.radioDest.setChecked(self.node.imagemode == IMAGEMODE_DEST)
        self.w.radioResult.setChecked(self.node.imagemode == IMAGEMODE_RESULT)
        self.w.checkBoxSrc.setChecked(self.node.showSrc)
        self.w.checkBoxDest.setChecked(self.node.showDest)

        self.w.canvas.display(self.node.canvimg)

    def canvasKeyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k == Qt.Key_M:
            self.mark()
            self.node.imagemode += 1
            self.node.imagemode %= IMAGEMODE_CT
            self.changed()
        elif k == Qt.Key_S:
            self.mark()
            self.node.showSrc = not self.node.showSrc
            self.changed()
        elif k == Qt.Key_D:
            self.mark()
            self.node.showDest = not self.node.showDest
            self.changed()
        elif k == Qt.Key_Delete:
            self.mark()
            self.node.type.delSelPoint(self.node)
            self.changed()

    def canvasMouseMoveEvent(self, x, y, e):
        if self.mouseDown:
            if self.node.type.moveSelPoint(self.node, x, y):
                self.changed()

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        self.mark()
        if e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier):
            # modifiers = we're adding
            if self.node.showSrc and self.node.showDest:
                # if both are shown, distinguish with modifier
                if e.modifiers() & Qt.ShiftModifier:  # shift = source
                    logger.debug("Adding SOURCE")
                    self.node.type.addPoint(self.node, x, y, False)
                elif e.modifiers() & Qt.ControlModifier:  # ctrl = dest
                    logger.debug("Adding DEST")
                    self.node.type.addPoint(self.node, x, y, True)
            else:
                # otherwise which sort we are adding can be determined from which sort
                # we are showing.
                if self.node.showSrc:
                    self.node.type.addPoint(self.node, x, y, False)
                elif self.node.showDest:
                    self.node.type.addPoint(self.node, x, y, True)
        else:
            # no modifiers, just select.
            self.node.type.selPoint(self.node, x, y)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
