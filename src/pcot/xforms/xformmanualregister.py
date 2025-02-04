import cv2 as cv
import numpy as np
from PySide2.QtCore import Qt
from PySide2.QtGui import QKeyEvent
from PySide2.QtWidgets import QMessageBox
from skimage import transform
from skimage.transform import warp, AffineTransform

from pcot.datum import Datum
import pcot.ui.tabs
from pcot.dq import NODATA, NOUNCERTAINTY
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType, taggedPointListType, taggedPointType
from pcot.utils import text, image
from pcot.xform import XFormType, xformtype, XFormException

IMAGEMODE_MOVING = 0
IMAGEMODE_FIXED = 1
IMAGEMODE_RESULTMOVING = 2
IMAGEMODE_RESULTFIXED = 3

IMAGEMODE_CT = 4

# These are the available homographies (see node doc), in the same order as they appear in the combobox.
homographies = [
    "euclidean",
    "similarity",
    "affine",
    "projective",
]


# channel-agnostic RGB of an image
def convertToRGB(img: ImageCube) -> np.array:
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
    Perform manual registration of two images. One input image is designated as "fixed", the other as "moving".

    The node will find a transform that maps the moving image onto the fixed image, and a translation that
    will ensure that both images remain uncropped. The fixed image will be translated only, the moving image
    will be transformed and then translated. Both transformed images are output and can then be merged or overlaid
    in a separate node.

    The transform is found by designating points in each image which correspond to each other. The number of points
    must be the same in each image, and at least three (unless "translate only" is selected).

    The canvas view can show the moving input, the fixed image, the transformed moving image, or the transformed fixed
    image. All images are shown as greyscale (since the input images will likely have different frequency bands).

    The transform used is one of the following homographies:

    * Euclidean - translation and rotation only
    * Similarity - translation, rotation, and scaling; angles are preserved
    * Affine - translation, rotation, scaling, and shearing; parallel lines are preserved
    * Projective - translation, rotation, scaling, shearing, and perspective; straight lines are preserved

    Points are added to the moving image by clicking with ctrl.
    Points are adding to the fixed image by clicking with shift.

    If only the moving or fixed points are shown, either shift- or ctrl-clicking will add to the appropriate
    point set. The selected point can be deleted with the Delete key (but this will modify the numbering!)

    **Note that this node does not currently display DQ or uncertainty data in its canvas**

    A point can be selected and dragged by clicking on it. This may be slow because the warping operation will
    take place every update; disabling 'auto-run on change' is a good idea!

    Uncertainty is warped along with the original image, as is DQ using nearest-neighbour (**which may not be
    sufficient**).

    """

    def __init__(self):
        super().__init__("manual register", "processing", "0.0.0")
        self.addInputConnector("moving", Datum.IMG)
        self.addInputConnector("fixed", Datum.IMG)
        self.addOutputConnector("moving", Datum.IMG)
        self.addOutputConnector("fixed", Datum.IMG)

        # IMPORTANT NOTE - this uses a mixture of plain params and Complex TaggedAggregate Serialisation.
        # All parameters except moving and fixed (point lists) are used directly. THe moving and fixed lists
        # are kept in the node, and processed using CTAS.

        self.params = TaggedDictType(
            showMoving=("Show moving points", bool, True),
            showFixed=("Show fixed points", bool, True),
            translate=("Translate only - no other transform. Uses a single point.", bool, False),
            moving=("Moving points", taggedPointListType),
            fixed=("Fixed points", taggedPointListType),
            transform=("Transform type", str, homographies[0], homographies),
        )

    def init(self, node):
        # these are stored in the node because they need to survive a uichange when doApply is False.
        node.movingOut = None
        node.fixedOut = None
        node.imagemode = IMAGEMODE_MOVING
        node.canvimg = None

        node.moving = []
        node.fixed = []

        # index of selected points
        node.selIdx = None
        # is the selected point (if any) in the fixed list (or the moving list)?
        node.selIsFixed = False

    def serialise(self, node):
        node.params.moving = taggedPointListType.create()
        node.params.fixed = taggedPointListType.create()

        for p in node.moving:
            dd = taggedPointType.create()
            dd.set(*p)
            node.params.moving.append(dd)
        for p in node.fixed:
            dd = taggedPointType.create()
            dd.set(*p)
            node.params.fixed.append(dd)

    def nodeDataFromParams(self, node):
        node.moving = []
        for p in node.params.moving:
            node.moving.append(p.get())
        node.fixed = []
        for p in node.params.fixed:
            node.fixed.append(p.get())

    def uichange(self, node):
        node.timesPerformed += 1
        self.perform(node, False)

    def perform(self, node, doApply=True):
        """Perform node. When called from uichange(), doApply will be False. Normally it's true."""
        movingImg = node.getInput(0, Datum.IMG)
        fixedImg = node.getInput(1, Datum.IMG)

        params = node.params

        if fixedImg and movingImg:
            if doApply:
                # only change these when apply happens - they should survive a uichange
                # when doApply is False.
                self.apply(node, fixedImg, movingImg)

            # this gets the appropriate image and also manipulates it.
            # Generally we convert RGB to grey; otherwise we'd have to store
            # quite a few mappings.
            if node.imagemode == IMAGEMODE_FIXED:
                canvimg = convertToRGB(fixedImg)
            elif node.imagemode == IMAGEMODE_MOVING:
                canvimg = convertToRGB(movingImg)
            elif node.imagemode == IMAGEMODE_RESULTMOVING:
                canvimg = None if node.movingOut is None else convertToRGB(node.movingOut)
            else:
                canvimg = None if node.fixedOut is None else convertToRGB(node.fixedOut)

            if canvimg is not None:
                # create a new image for the canvas; we'll draw on it.
                canvimg = image.imgmerge([canvimg, canvimg, canvimg])

                # now draw the points

                if params.showMoving:
                    issel = node.selIdx if not node.selIsFixed else None
                    drawpoints(canvimg, node.moving, params.translate, issel, (1, 1, 0))
                if params.showFixed:
                    issel = node.selIdx if node.selIsFixed else None
                    drawpoints(canvimg, node.fixed, params.translate, issel, (0, 1, 1))

                # grey, but 3 channels so I can draw on it!
                node.canvimg = ImageCube(canvimg, node.mapping, None)
            else:
                node.canvimg = None     # redundant, but helps with debugging.

        node.setOutput(0, Datum(Datum.IMG, node.movingOut))
        node.setOutput(1, Datum(Datum.IMG, node.fixedOut))

    @staticmethod
    def delSelPoint(n):
        if n.selIdx is not None:
            if n.params.showMoving and not n.selIsFixed:
                del n.moving[n.selIdx]
                n.selIdx = None
            elif n.params.showFixed and n.selIsFixed:
                del n.fixed[n.selIdx]
                n.selIdx = None

    @staticmethod
    def moveSelPoint(n, x, y):
        if n.selIdx is not None:
            if n.params.showMoving and not n.selIsFixed:
                n.moving[n.selIdx] = (x, y)
                return True
            elif n.params.showFixed and n.selIsFixed:
                n.fixed[n.selIdx] = (x, y)
                return True
        return False

    @staticmethod
    def addPoint(n, x, y, fixed):
        lst = n.fixed if fixed else n.moving
        # translate mode changes the first point, or adds a point if there isn't one.
        if len(lst) == 0 or not n.params.translate:
            lst.append((x, y))
        else:
            lst[0] = (x, y)

    @staticmethod
    def selPoint(n, x, y):
        pt = None
        if n.params.showMoving:
            pt = findInList(n.moving, x, y, n.params.translate)
            if pt is not None:
                n.selIdx = pt
                n.selIsFixed = False
        if pt is None and n.params.showFixed:
            pt = findInList(n.fixed, x, y, n.params.translate)
            if pt is not None:
                n.selIdx = pt
                n.selIsFixed = True

    @staticmethod
    def apply(n, fixedImg, movingImg):
        # errors here must not be thrown, we need later stuff to run - we'll raise the exception and catch it
        # later.
        try:
            if len(n.moving) != len(n.fixed):
                raise XFormException('DATA', "Number of moving and fixed points must be the same")
            if n.params.translate:
                if len(n.moving) < 1:
                    raise XFormException('DATA', "There must be a reference point in translate mode")
                moving = n.moving[0]
                fixed = n.fixed[0]
                d = (moving[0]-fixed[0], moving[1]-fixed[1])
                tform = transform.EuclideanTransform(translation=(d[0], d[1]))
            else:
                if len(n.moving) < 3:
                    raise XFormException('DATA', "There must be at least three points")
                if n.params.transform == "euclidean":
                    tform = transform.EuclideanTransform()
                elif n.params.transform == "similarity":
                    tform = transform.SimilarityTransform()
                elif n.params.transform == "affine":
                    tform = transform.AffineTransform()
                elif n.params.transform == "projective":
                    tform = transform.ProjectiveTransform()
                else:
                    raise XFormException('DATA', "Unknown transform type")
                tform.estimate(np.array(n.fixed), np.array(n.moving))

            # we now have our transform, and it is assumed we have images. We will move the 'moving' image into the
            # coordinate system of the "fixed" image, but we may also move the "fixed" image into a new basis which
            # differs from the original by a translation alone.

            # work out the bounding box of the transformed moving image
            maxy,maxx = movingImg.h-1, movingImg.w-1
            corners = np.array([[0,0], [0,maxy], [maxx,0], [maxx,maxy]])
            # transform the corners by the inverse transform - I'm really not at all sure why this needs to be inverted.
            transformed_corners = tform.inverse(corners)

            # Get the min and max coordinates for the bounding box of the transformed corners
            # of the moving image
            min_x1, min_y1 = transformed_corners.min(axis=0)
            max_x1, max_y1 = transformed_corners.max(axis=0)

            # now use this to calculate the COMBINED bb - this is the MOVING BB intersected with
            # the FIXED BB (which is just (0,0),(maxw,maxh) for that image).

            min_combined_x = min(min_x1, 0)
            min_combined_y = min(min_y1, 0)
            max_combined_x = max(max_x1, fixedImg.w - 1)
            max_combined_y = max(max_y1, fixedImg.h - 1)

            # Calculate the output shape, ensuring both images will fit
            output_height = int(np.ceil(max_combined_y - min_combined_y))
            output_width = int(np.ceil(max_combined_x - min_combined_x))

            # Make a translation that will be applied to both fixed and moving image to get
            # them into the same coordinate system. Also make the final transform for the moving image,
            # that needs to be applied before the translation.
            # Again, I sort of feel that these should be negative...
            translation = AffineTransform(translation=(min_combined_x, min_combined_y))
            moving_xform = translation + tform

            # apply the transformation to the moving image
            img = warp(movingImg.img, moving_xform, preserve_range=True,
                       output_shape=(output_height,output_width)).astype(np.float32)
            unc = warp(movingImg.uncertainty, moving_xform, preserve_range=True,
                       output_shape=(output_height,output_width)).astype(np.float32)
            # DQ warp is nearest neighbour (order=0). Make sure we fill absent areas with NODATA.
            dq = warp(movingImg.dq, moving_xform, order=0, preserve_range=True,
                      output_shape=(output_height,output_width),
                      cval=NODATA|NOUNCERTAINTY, mode='constant').astype(np.uint16)

            n.movingOut = ImageCube(img, movingImg.mapping, movingImg.sources, uncertainty=unc, dq=dq)

            # apply only the translation to the fixed image
            img = warp(fixedImg.img, translation, preserve_range=True,
                          output_shape=(output_height,output_width)).astype(np.float32)
            unc = warp(fixedImg.uncertainty, translation, preserve_range=True,
                            output_shape=(output_height,output_width)).astype(np.float32)
            # DQ warp is nearest neighbour (order=0). Make sure we fill absent areas with NODATA.
            dq = warp(fixedImg.dq, translation, order=0, preserve_range=True,
                        output_shape=(output_height,output_width),
                        cval=NODATA|NOUNCERTAINTY, mode='constant').astype(np.uint16)

            n.fixedOut = ImageCube(img, fixedImg.mapping, fixedImg.sources, uncertainty=unc, dq=dq)

        except XFormException as e:
            # handle any errors by setting the node error and returning no images
            n.setError(e)

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

        self.w.radioMoving.toggled.connect(self.radioViewToggled)
        self.w.radioFixed.toggled.connect(self.radioViewToggled)
        self.w.radioResultMoving.toggled.connect(self.radioViewToggled)
        self.w.radioResultFixed.toggled.connect(self.radioViewToggled)
        self.w.translate.toggled.connect(self.translateToggled)

        self.w.checkBoxFixed.toggled.connect(self.checkBoxFixedToggled)
        self.w.checkBoxMoving.toggled.connect(self.checkBoxMovingToggled)
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
            self.node.fixed = []
            self.node.moving = []
            self.node.selIdx = None
            self.changed()

    def radioViewToggled(self):
        self.mark()
        if self.w.radioMoving.isChecked():
            self.node.imagemode = IMAGEMODE_MOVING
        elif self.w.radioFixed.isChecked():
            self.node.imagemode = IMAGEMODE_FIXED
        elif self.w.radioResultMoving.isChecked():
            self.node.imagemode = IMAGEMODE_RESULTMOVING
        elif self.w.radioResultFixed.isChecked():
            self.node.imagemode = IMAGEMODE_RESULTFIXED
        self.changed(uiOnly=True)

    def checkBoxFixedToggled(self):
        self.mark()
        self.node.params.showFixed = self.w.checkBoxFixed.isChecked()
        self.changed(uiOnly=True)

    def checkBoxMovingToggled(self):
        self.mark()
        self.node.params.showMoving = self.w.checkBoxMoving.isChecked()
        self.changed(uiOnly=True)

    def translateToggled(self):
        self.mark()
        self.node.params.translate = self.w.translate.isChecked()
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        self.w.radioMoving.setChecked(self.node.imagemode == IMAGEMODE_MOVING)
        self.w.radioFixed.setChecked(self.node.imagemode == IMAGEMODE_FIXED)
        self.w.radioResultMoving.setChecked(self.node.imagemode == IMAGEMODE_RESULTMOVING)
        self.w.radioResultFixed.setChecked(self.node.imagemode == IMAGEMODE_RESULTFIXED)

        self.w.checkBoxMoving.setChecked(self.node.params.showMoving)
        self.w.checkBoxFixed.setChecked(self.node.params.showFixed)
        self.w.translate.setChecked(self.node.params.translate)
        self.w.transformCombo.setCurrentIndex(homographies.index(self.node.params.transform))

        # displaying a premapped image
        self.w.canvas.display(self.node.canvimg, self.node.canvimg, self.node)

    def canvasKeyPressEvent(self, e: QKeyEvent):
        k = e.key()
        if k == Qt.Key_D:   # image display mode change
            self.mark()
            self.node.imagemode += 1
            self.node.imagemode %= IMAGEMODE_CT
            self.changed()
        elif k == Qt.Key_M:  # show moving points toggle
            self.mark()
            self.node.params.showMoving = not self.node.params.showMoving
            self.changed()
        elif k == Qt.Key_F:  # show fixed points toggle
            self.mark()
            self.node.params.showFixed = not self.node.params.showFixed
            self.changed()
        elif k == Qt.Key_Delete:    # delete point
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
            if self.node.params.showMoving and self.node.params.showFixed:
                # if both are shown, distinguish with modifier
                if e.modifiers() & Qt.ControlModifier:  # ctrl = moving
                    self.node.type.addPoint(self.node, x, y, False)
                elif e.modifiers() & Qt.ShiftModifier:  # shift = fixed
                    self.node.type.addPoint(self.node, x, y, True)
            else:
                # otherwise which sort we are adding can be determined from which sort
                # we are showing.
                if self.node.params.showMoving:
                    self.node.type.addPoint(self.node, x, y, False)
                elif self.node.params.showFixed:
                    self.node.type.addPoint(self.node, x, y, True)
        else:
            # no modifiers, just select.
            self.node.type.selPoint(self.node, x, y)
        self.changed()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self, x, y, e):
        self.mouseDown = False
