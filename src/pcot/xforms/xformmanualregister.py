import cv2 as cv
import numpy as np
from PySide2.QtCore import Qt
from PySide2.QtGui import QKeyEvent
from PySide2.QtWidgets import QMessageBox
from skimage import transform
from skimage.transform import warp

from pcot.datum import Datum
import pcot.ui.tabs
from pcot.dq import NODATA, NOUNCERTAINTY
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType, taggedPointListType, taggedPointType
from pcot.utils import text, image
from pcot.xform import XFormType, xformtype, XFormException

IMAGEMODE_SOURCE = 0
IMAGEMODE_DEST = 1
IMAGEMODE_RESULT = 2

IMAGEMODE_CT = 3

# These are the available homographies (see node doc), in the same order as they appear in the combobox.
homographies = [
    "euclidean",
    "similarity",
    "affine",
    "projective",
]


# channel-agnostic RGB of an image
def prep(img: ImageCube) -> np.array:
    mat = np.array([1 / img.channels] * img.channels).reshape((1, img.channels))
    canvimg = cv.transform(img.img, mat)
    mn = np.min(canvimg)
    mx = np.max(canvimg)
    return (canvimg - mn) / (mx - mn)


def drawpoints(img, lst, translate, selidx, col):
    i = 0
    thickness = 2
    fontsize = 10

    if translate:
        # translate-only mode uses only one point, don't show the others
        if len(lst) > 1:
            lst = [lst[0]]

    for p in lst:
        cv.circle(img, p, 7, col, thickness)
        x, y = p
        text.write(img, str(i), x + 10, y + 10, False, fontsize, thickness, col)
        i = i + 1

    if selidx is not None:
        cv.circle(img, lst[selidx], 10, col, thickness + 2)


def findInList(lst, x, y, translate):
    pt = None
    mindist = None

    limit = len(lst)
    if translate:
        limit = min(limit, 1)  # in translate mode, only look at the first item
    for idx in range(limit):
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
    Perform manual registration of two images. The output is a version of the 'moving' image with a
    transform applied to map points onto corresponding points in the 'fixed' image.

    The canvas view can show the moving input (also referred to as the "source"), the fixed image (also referred
    to as the "destination"), a blend of the two, or the result. All images are shown as greyscale (since the
    fixed and moving images will likely have different frequency bands).

    The transform will map a set of points in the moving image onto a set in the fixed image. Both sets of
    points can be changed, or a single set. Points are mapped onto the correspondingly numbered point. In "translate"
    mode only a single point is required (and only a single point will be shown from each set).

    The transform used is one of the following homographies:

    * Euclidean - translation and rotation only
    * Similarity - translation, rotation, and scaling; angles are preserved
    * Affine - translation, rotation, scaling, and shearing; parallel lines are preserved
    * Projective - translation, rotation, scaling, shearing, and perspective; straight lines are preserved

    Points are added to the source (moving) image by clicking with shift.
    Points are adding to the dest (fixed) image by clicking with ctrl.

    **Note that this node does not currently display DQ or uncertainty data in its canvas**

    If only the source or dest points are shown, either shift- or ctrl-clicking will add to the appropriate
    point set. The selected point can be deleted with the Delete key (but this will modify the numbering!)

    A point can be selected and dragged by clicking on it. This may be slow because the warping operation will
    take place every update; disabling 'auto-run on change' is a good idea!

    Uncertainty is warped along with the original image, as is DQ using nearest-neighbour (**which may not be
    sufficient**).

    """

    def __init__(self):
        super().__init__("manual register", "processing", "0.0.0")
        self.addInputConnector("moving", Datum.IMG)
        self.addInputConnector("fixed", Datum.IMG)
        self.addOutputConnector("moved", Datum.IMG)

        # IMPORTANT NOTE - this uses a mixture of plain params and Complex TaggedAggregate Serialisation.
        # All parameters except src and dest (point lists) are used directly. THe src and dest lists
        # are kept in the node, and processed using CTAS.

        self.params = TaggedDictType(
            showSrc=("Show source points", bool, True),
            showDest=("Show destination points", bool, True),
            translate=("Translate only - no other transform. Uses a single point.", bool, False),
            src=("Source points", taggedPointListType),
            dest=("Destination points", taggedPointListType),
            transform=("Transform type", str, homographies[0], homographies),
        )

    def init(self, node):
        node.img = None     # this is one of the few nodes which does store .img in the node
        node.imagemode = IMAGEMODE_SOURCE
        node.canvimg = None

        node.src = []
        node.dest = []

        # index of selected points
        node.selIdx = None
        # is the selected point (if any) in the dest list (or the source list)?
        node.selIsDest = False

    def serialise(self, node):
        node.params.src = taggedPointListType.create()
        node.params.dest = taggedPointListType.create()

        for p in node.src:
            dd = taggedPointType.create()
            dd.set(*p)
            node.params.src.append(dd)
        for p in node.dest:
            dd = taggedPointType.create()
            dd.set(*p)
            node.params.dest.append(dd)

    def nodeDataFromParams(self, node):
        node.src = []
        for p in node.params.src:
            node.src.append(p.get())
        node.dest = []
        for p in node.params.dest:
            node.dest.append(p.get())

    def uichange(self, node):
        node.timesPerformed += 1
        self.perform(node, False)

    def perform(self, node, doApply=True):
        """Perform node. When called from uichange(), doApply will be False. Normally it's true."""
        movingImg = node.getInput(0, Datum.IMG)
        fixedImg = node.getInput(1, Datum.IMG)

        params = node.params

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
            else:
                if node.img is not None:
                    img = prep(node.img)
                else:
                    img = None

            node.movingImg = movingImg

            if img is not None:
                # create a new image for the canvas; we'll draw on it.
                canvimg = image.imgmerge([img, img, img])

                # now draw the points

                if params.showSrc:
                    issel = node.selIdx if not node.selIsDest else None
                    drawpoints(canvimg, node.src, params.translate, issel, (1, 1, 0))
                if params.showDest:
                    issel = node.selIdx if node.selIsDest else None
                    drawpoints(canvimg, node.dest, params.translate, issel, (0, 1, 1))

                # grey, but 3 channels so I can draw on it!
                node.canvimg = ImageCube(canvimg, node.mapping, None)
            else:
                node.canvimg = None

        node.setOutput(0, Datum(Datum.IMG, node.img))

    @staticmethod
    def delSelPoint(n):
        if n.selIdx is not None:
            if n.params.showSrc and not n.selIsDest:
                del n.src[n.selIdx]
                n.selIdx = None
            elif n.params.showDest and n.selIsDest:
                del n.dest[n.selIdx]
                n.selIdx = None

    @staticmethod
    def moveSelPoint(n, x, y):
        if n.selIdx is not None:
            if n.params.showSrc and not n.selIsDest:
                n.src[n.selIdx] = (x, y)
                return True
            elif n.params.showDest and n.selIsDest:
                n.dest[n.selIdx] = (x, y)
                return True
        return False

    @staticmethod
    def addPoint(n, x, y, dest):
        lst = n.dest if dest else n.src
        # translate mode changes the first point, or adds a point if there isn't one.
        if len(lst) == 0 or not n.params.translate:
            lst.append((x, y))
        else:
            lst[0] = (x, y)

    @staticmethod
    def selPoint(n, x, y):
        if n.showSrc:
            pt = findInList(n.src, x, y, n.params.translate)
            if pt is not None:
                n.selIdx = pt
                n.selIsDest = False
        if pt is None and n.showDest:
            pt = findInList(n.dest, x, y, n.params.translate)
            if pt is not None:
                n.selIdx = pt
                n.selIsDest = True

    @staticmethod
    def apply(n):
        # errors here must not be thrown, we need later stuff to run.
        if len(n.src) != len(n.dest):
            n.setError(XFormException('DATA', "Number of source and dest points must be the same"))
            return
        if n.params.translate:
            if len(n.src) < 1:
                n.setError(XFormException('DATA', "There must be a reference point in translate mode"))
                return
            src = n.src[0]
            dest = n.dest[0]
            d = (src[0]-dest[0], src[1]-dest[1])
            tform = transform.EuclideanTransform(translation=(d[0], d[1]))
        else:
            if len(n.src) < 3:
                n.setError(XFormException('DATA', "There must be at least three points"))
                return
            if n.params.transform == "euclidean":
                tform = transform.EuclideanTransform()
            elif n.params.transform == "similarity":
                tform = transform.SimilarityTransform()
            elif n.params.transform == "affine":
                tform = transform.AffineTransform()
            elif n.params.transform == "projective":
                tform = transform.ProjectiveTransform()
            else:
                n.setError(XFormException('DATA', "Unknown transform type"))
                return
            tform.estimate(np.array(n.dest), np.array(n.src))

        if n.movingImg is not None:
            img = warp(n.movingImg.img, tform, preserve_range=True).astype(np.float32)
            unc = warp(n.movingImg.img, tform, preserve_range=True).astype(np.float32)
            # DQ warp is nearest neighbour (order=0). Make sure we fill absent areas with NODATA.
            dq = warp(n.movingImg.dq, tform, order=0, preserve_range=True, cval=NODATA|NOUNCERTAINTY, mode='constant').astype(np.uint16)
            n.img = ImageCube(img, n.movingImg.mapping, n.movingImg.sources, uncertainty=unc, dq=dq)

    def createTab(self, n, w):
        return TabManualReg(n, w)

    def clearData(self, xform):
        xform.canvimg = None


class TabManualReg(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabmanreg.ui')
        self.mouseDown = False
        self.w.canvas.keyHook = self
        self.w.canvas.mouseHook = self

        self.nodeChanged()  # doing this FIRST so signals don't go to slots during setup.

        self.w.radioSource.toggled.connect(self.radioViewToggled)
        self.w.radioDest.toggled.connect(self.radioViewToggled)
        self.w.radioResult.toggled.connect(self.radioViewToggled)
        self.w.translate.toggled.connect(self.translateToggled)

        self.w.checkBoxDest.toggled.connect(self.checkBoxDestToggled)
        self.w.checkBoxSrc.toggled.connect(self.checkBoxSrcToggled)
        self.w.transformCombo.currentIndexChanged.connect(self.transformChanged)

        self.w.clearButton.clicked.connect(self.clearClicked)

    def transformChanged(self, i):
        self.mark()
        self.node.params.transform = homographies[i]
        self.changed()

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
        self.node.params.showDest = self.w.checkBoxDest.isChecked()
        self.changed(uiOnly=True)

    def checkBoxSrcToggled(self):
        self.mark()
        self.node.params.showSrc = self.w.checkBoxSrc.isChecked()
        self.changed(uiOnly=True)

    def translateToggled(self):
        self.mark()
        self.node.params.translate = self.w.translate.isChecked()
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        self.w.radioSource.setChecked(self.node.imagemode == IMAGEMODE_SOURCE)
        self.w.radioDest.setChecked(self.node.imagemode == IMAGEMODE_DEST)
        self.w.radioResult.setChecked(self.node.imagemode == IMAGEMODE_RESULT)

        self.w.checkBoxSrc.setChecked(self.node.params.showSrc)
        self.w.checkBoxDest.setChecked(self.node.params.showDest)
        self.w.translate.setChecked(self.node.params.translate)
        self.w.transformCombo.setCurrentIndex(homographies.index(self.node.params.transform))

        # displaying a premapped image
        self.w.canvas.display(self.node.canvimg, self.node.canvimg, self.node)

    def canvasKeyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k == Qt.Key_M:
            self.mark()
            self.node.imagemode += 1
            self.node.imagemode %= IMAGEMODE_CT
            self.changed()
        elif k == Qt.Key_S:
            self.mark()
            self.node.params.showSrc = not self.node.params.showSrc
            self.changed()
        elif k == Qt.Key_D:
            self.mark()
            self.node.params.showDest = not self.node.params.showDest
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
            if self.node.params.showSrc and self.node.params.showDest:
                # if both are shown, distinguish with modifier
                if e.modifiers() & Qt.ShiftModifier:  # shift = source
                    self.node.type.addPoint(self.node, x, y, False)
                elif e.modifiers() & Qt.ControlModifier:  # ctrl = dest
                    self.node.type.addPoint(self.node, x, y, True)
            else:
                # otherwise which sort we are adding can be determined from which sort
                # we are showing.
                if self.node.params.showSrc:
                    self.node.type.addPoint(self.node, x, y, False)
                elif self.node.params.showDest:
                    self.node.type.addPoint(self.node, x, y, True)
        else:
            # no modifiers, just select.
            self.node.type.selPoint(self.node, x, y)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
