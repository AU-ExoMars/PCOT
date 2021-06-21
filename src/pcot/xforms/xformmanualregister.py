import cv2 as cv
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QMessageBox
from skimage import transform
from skimage.transform import warp

import pcot.conntypes as conntypes
import pcot.ui.tabs
from pcot.channelsource import REDINTERNALSOURCE, GREENINTERNALSOURCE, \
    BLUEINTERNALSOURCE
from pcot.pancamimage import ImageCube
from pcot.utils import text
from pcot.xform import XFormType, xformtype, XFormException

IMAGEMODE_SOURCE = 0
IMAGEMODE_DEST = 1
IMAGEMODE_BOTH = 2
IMAGEMODE_RESULT = 3

IMAGEMODE_CT = 4


# channel-agnostic RGB of an image
def prep(img: ImageCube) -> np.array:
    mat = np.array([1 / img.channels] * img.channels).reshape((1, img.channels))
    canvimg = cv.transform(img.img, mat)
    mn = np.min(canvimg)
    mx = np.max(canvimg)
    return (canvimg - mn) / (mx - mn)


def drawpoints(img, lst, selidx, col):
    i = 0
    fontline = 2
    fontsize = 10

    for p in lst:
        cv.circle(img, p, 7, col, fontline)
        x, y = p
        text.write(img, str(i), x + 10, y + 10, False, fontsize, fontline, col)
        i = i + 1

    if selidx is not None:
        cv.circle(img, lst[selidx], 10, col, fontline + 2)


def findInList(lst, x, y):
    pt = None
    mindist = None
    for idx in range(len(lst)):
        px, py = lst[idx]
        dx = px - x
        dy = py - y
        dsq = dx * dx + dy * dy
        if dsq < 100 and (mindist is None or dsq < mindist):
            pt = idx
            mindist = dsq
    return pt


@xformtype
class XFormManualRegister(XFormType):
    """
    Perform manual registration of two images. The output is a version of the 'moving' image with a projective
    transform applied to map points onto corresponding points in the 'fixed' image.

    The canvas view can show the moving input (also referred to as the "source"), the fixed image (also referred
    to as the "destination"), a blend of the two, or the result. All images are shown as greyscale (since the
    fixed and moving images will likely have different frequency bands).

    The transform will map a set of points in the moving image onto a set in the fixed image. Both sets of
    points can be changed, or a single set. Points are mapped onto the correspondingly numbered point.

    Points are added to the source (moving) image by clicking with shift.
    Points are adding to the dest (fixed) image by clicking with alt.

    If only the source or dest points are shown, either shift- or alt-clicking will add to the appropriate
    point set. The selected point can be deleted with the Delete key (but this will modify the numbering!)

    A point can be selected and dragged by clicking on it. This may be slow because the warping operation will
    take place every update; disabling 'auto-run on change' is a good idea!

    """
    def __init__(self):
        super().__init__("manual register", "processing", "0.0.0")
        self.addInputConnector("moving", conntypes.IMG)
        self.addInputConnector("fixed", conntypes.IMG)
        self.addOutputConnector("moved", conntypes.IMG)
        self.autoserialise = ('showSrc', 'showDest', 'src', 'dest')

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

    def uichange(self, node):
        self.perform(node, False)

    def perform(self, node, doApply=True):
        # read images
        movingImg = node.getInput(0, conntypes.IMG)
        fixedImg = node.getInput(1, conntypes.IMG)

        if fixedImg is None or movingImg is None:
            node.img = None  # output image (i.e. warped)
            node.movingImg = None  # image we are moving
        else:
            if doApply:
                self.apply(node)

            # this gets the appropriate image and also manipulates it.
            # Generally we convert RGB to grey; otherwise we'd have to store
            # quite a few mappings.
            if node.imagemode == IMAGEMODE_DEST:
                img = prep(fixedImg)
            elif node.imagemode == IMAGEMODE_SOURCE:
                img = prep(movingImg)
            elif node.imagemode == IMAGEMODE_RESULT:
                if node.img is not None:
                    img = prep(node.img)
                else:
                    img = None
            else:
                img = (prep(movingImg) + prep(fixedImg)) / 2

            node.movingImg = movingImg

            if img is not None:
                # create a new image for the canvas; we'll draw on it.
                canvimg = cv.merge([img, img, img])

                # now draw the points

                if node.showSrc:
                    issel = node.selIdx if not node.selIsDest else None
                    drawpoints(canvimg, node.src, issel, (1, 1, 0))
                if node.showDest:
                    issel = node.selIdx if node.selIsDest else None
                    drawpoints(canvimg, node.dest, issel, (0, 1, 1))

                # grey, but 3 channels so I can draw on it!
                node.canvimg = ImageCube(canvimg, node.mapping,
                                         [{REDINTERNALSOURCE}, {GREENINTERNALSOURCE}, {BLUEINTERNALSOURCE}])
            else:
                node.canvimg = None

        node.setOutput(0, conntypes.Datum(conntypes.IMG, node.img))

    def slowPerform(self, xform):
        self.perform(xform, slow=True)

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
        (n.dest if dest else n.src).append((x, y))

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
    def apply(n):
        # errors here must not be thrown, we need later stuff to run.
        if len(n.src) != len(n.dest):
            n.setError(XFormException('DATA', "Number of source and dest points must be the same"))
        elif len(n.src) < 3:
            n.setError(XFormException('DATA', "There must be at least three points"))
        else:
            tform = transform.ProjectiveTransform()
            tform.estimate(np.array(n.dest), np.array(n.src))

            if n.movingImg is not None:
                img = warp(n.movingImg.img, tform)
                n.img = ImageCube(img, n.movingImg.mapping, n.movingImg.sources)

    def createTab(self, n, w):
        return TabManualReg(n, w)


class TabManualReg(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabmanreg.ui')
        self.mouseDown = False
        self.w.canvas.setGraph(node.graph)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setPersister(node)
        self.w.canvas.keyHook = self
        self.w.canvas.mouseHook = self

        self.onNodeChanged()  # doing this FIRST so signals don't go to slots during setup.

        self.w.radioBoth.toggled.connect(self.radioViewToggled)
        self.w.radioSource.toggled.connect(self.radioViewToggled)
        self.w.radioDest.toggled.connect(self.radioViewToggled)
        self.w.radioResult.toggled.connect(self.radioViewToggled)

        self.w.checkBoxDest.toggled.connect(self.checkBoxDestToggled)
        self.w.checkBoxSrc.toggled.connect(self.checkBoxSrcToggled)

        self.w.clearButton.clicked.connect(self.clearClicked)

    def clearClicked(self):
        if QMessageBox.question(self.parent(), "Clear all points", "Are you sure?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.node.dest = []
            self.node.src = []
            self.node.selIdx = None
            self.changed()

    def radioViewToggled(self):
        if self.w.radioBoth.isChecked():
            self.node.imagemode = IMAGEMODE_BOTH
        elif self.w.radioSource.isChecked():
            self.node.imagemode = IMAGEMODE_SOURCE
        elif self.w.radioDest.isChecked():
            self.node.imagemode = IMAGEMODE_DEST
        elif self.w.radioResult.isChecked():
            self.node.imagemode = IMAGEMODE_RESULT
        self.changed(uiOnly=True)

    def checkBoxDestToggled(self):
        self.node.showDest = self.w.checkBoxDest.isChecked()
        self.changed(uiOnly=True)

    def checkBoxSrcToggled(self):
        self.node.showSrc = self.w.checkBoxSrc.isChecked()
        self.changed(uiOnly=True)

    def onNodeChanged(self):
        self.w.radioBoth.setChecked(self.node.imagemode == IMAGEMODE_BOTH)
        self.w.radioSource.setChecked(self.node.imagemode == IMAGEMODE_SOURCE)
        self.w.radioDest.setChecked(self.node.imagemode == IMAGEMODE_DEST)
        self.w.radioResult.setChecked(self.node.imagemode == IMAGEMODE_RESULT)

        self.w.checkBoxSrc.setChecked(self.node.showSrc)
        self.w.checkBoxDest.setChecked(self.node.showDest)

        # displaying a premapped image
        self.w.canvas.display(self.node.canvimg, self.node.canvimg, self.node)

    def canvasKeyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k == Qt.Key_M:
            self.node.imagemode += 1
            self.node.imagemode %= IMAGEMODE_CT
            self.changed()
        elif k == Qt.Key_S:
            self.node.showSrc = not self.node.showSrc
            self.changed()
        elif k == Qt.Key_D:
            self.node.showDest = not self.node.showDest
            self.changed()
        elif k == Qt.Key_Delete:
            self.node.type.delSelPoint(self.node)
            self.changed()

    def canvasMouseMoveEvent(self, x, y, e):
        if self.mouseDown:
            if self.node.type.moveSelPoint(self.node, x, y):
                self.changed()

    def canvasMousePressEvent(self, x, y, e):
        self.mouseDown = True
        if e.modifiers() & (Qt.ShiftModifier | Qt.AltModifier):
            # modifiers = we're adding
            if self.node.showSrc and self.node.showDest:
                # if both are shown, distinguish with modifier
                if e.modifiers() & Qt.ShiftModifier:  # shift = source
                    self.node.type.addPoint(self.node, x, y, False)
                elif e.modifiers() & Qt.AltModifier:  # alt = dest
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
