from typing import Callable, Tuple

import cv2 as cv
import numpy as np
from PySide2.QtCore import Qt, QPointF
from PySide2.QtGui import QPainter, QImage
from numpy import ndarray
from scipy import ndimage

from pcot.sources import SourcesObtainable, nullSourceSet
from pcot.utils import text, serialiseFields, deserialiseFields
from pcot.utils.annotations import Annotation, annotDrawText
from pcot.utils.colour import rgb2qcol
from pcot.utils.geom import Rect


class BadOpException(Exception):
    def __init__(self):
        super().__init__("op not valid")


class ROIBoundsException(Exception):
    def __init__(self):
        super().__init__(
            "ROI is out of bounds or entirely outside image. Have you loaded a new image?")


ROISERIALISEFIELDS = ['label', 'labeltop', 'colour', 'fontline', 'fontsize', 'drawbg']


class ROI(SourcesObtainable, Annotation):
    """definition of base type for regions of interest - this is useful in itself
    because it defines an ROI consisting of a predefined BB and mask."""

    def __init__(self, tpname, bbrect: Rect = None, maskimg: np.array = None):
        """Ctor. ROIs have a label, which is used to label data in nodes like 'spectrum' and appears in annotations"""
        self.label = None
        self.bbrect = bbrect
        self.bbrect = bbrect
        self.maskimg = maskimg
        self.tpname = tpname  # subtype name (e.g. 'rect', 'poly')

        self.labeltop = False  # draw the label at the top?
        self.colour = (1, 1, 0)  # annotation colour
        self.fontline = 2  # thickness of lines and text
        self.fontsize = 10  # annotation font size
        self.drawbg = True
        # by default, the source of an ROI is null.
        # The only time this might not be true is if the ROI is derived somehow from an actual data source.
        self.sources = nullSourceSet

    def setDrawProps(self, labeltop, colour, fontsize, fontline, drawbg):
        """set the common draw properties for all ROIs"""
        self.labeltop = labeltop
        self.colour = colour
        self.fontline = fontline
        self.fontsize = fontsize
        self.drawbg = drawbg

    def bb(self):
        """return a Rect describing the bounding box for this ROI"""
        return self.bbrect

    def crop(self, img):
        """return an image cropped to the BB"""
        x, y, x2, y2 = self.bb().corners()
        return img.img[y:y2, x:x2]

    def mask(self):
        """return a boolean mask which, when imposed on the cropped image, gives the ROI. Or none in which case there is no mask.
        Note that this is an inverted mask from how masked arrays in numpy work: true means the pixel is included.
        """
        return self.maskimg

    def pixels(self):
        """count the number of pixels in the ROI"""
        if self.bb() is None:
            return 0  # ROI is degenerate or inactive
        else:
            return self.mask().sum()

    def details(self):
        """Information string on this ROI. This default shows the extent."""
        bb = self.bb()
        if bb is not None:
            x, y, w, h = bb
            return "{} pixels\n{},{}\n{}x{}".format(self.pixels(),
                                                    x, y, w, h)
        else:
            return "No ROI"

    def annotateBB(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        """Draw the BB onto a QPainter"""
        if (bb := self.bb()) is not None:
            x, y, w, h = bb.astuple()
            x, y = mapcoords(x, y)
            p.setBrush(Qt.NoBrush)
            p.setPen(rgb2qcol(self.colour))
            p.drawRect(x, y, w / scale, h / scale)

    def annotateMask(self, p: QPainter,
                     scale: float,
                     mapcoords: Callable[[float, float], Tuple[float, float]],
                     drawEdge=False):
        """This is the 'default' annotate, which draws the ROI onto the painter by
        using its actual mask. It takes the mask, edge detects (if drawEdge), converts into
        an image."""
        if (bb := self.bb()) is not None:
            # now get the mask
            mask = self.mask()
            # run sobel edge-detection on it if required
            if drawEdge:
                sx = ndimage.sobel(mask, axis=0, mode='constant')
                sy = ndimage.sobel(mask, axis=1, mode='constant')
                mask = np.hypot(sx, sy)
            mask = mask.clip(max=1.0).astype(np.float)
            ww = int(bb.w / scale)
            hh = int(bb.h / scale)
            mask = cv.resize(mask, dsize=(ww, hh), interpolation=cv.INTER_AREA)
            # does a little dilation
            # now prepare the actual image, which is just a coloured fill rectangle (we'll add alpha)
            img = np.full((hh, ww, 3), [1, 1, 0], dtype=np.float)  # the second arg is the colour
            # add the alpha channel
            x = np.dstack((img, mask))
            # to byte
            x = (x * 255).astype(np.ubyte)
            # resize to canvas/painter scale
            # to qimage, stashing the data into a field to avoid the problem
            # discussed in canvas.img2qimage where memory is freed by accident in Qt
            # (https://bugreports.qt.io/browse/PYSIDE-1563)
            self.workaround = x
            q = QImage(x.data, ww, hh, ww * 4, QImage.Format_RGBA8888)
            # now we have a QImage we can draw it onto the painter.
            xx, yy = mapcoords(bb.x, bb.y)
            p.drawImage(xx, yy, q)

    def annotateText(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        """Draw the text for the ROI onto the painter"""
        if (bb := self.bb()) is not None and self.fontsize > 0 and self.label is not None and self.label != '':
            x, y, x2, y2 = bb.corners()
            ty = y if self.labeltop else y2
            x, ty = mapcoords(x, ty)
            # basetop is the neg of labeltop because if the label is at the TOP,
            # the base of the text is y coord.
            annotDrawText(p, x, ty, self.label, self.colour,
                          basetop=not self.labeltop,
                          bgcol=(0, 0, 0) if self.drawbg else None,
                          fontsize=self.fontsize)

    def annotate(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        """This is the default annotation method drawing the ROI onto a QPainter as part of the annotations system.
        It should be replaced with a more specialised method if possible."""
        self.annotateBB(p, scale, mapcoords)
        self.annotateText(p, scale, mapcoords)
        self.annotateMask(p, scale, mapcoords, drawEdge=True)

    def baseDraw(self, img: ndarray, drawBox=False, drawEdge=True):
        """Draw the ROI onto an RGB image using the set colour (yellow by default)"""
        # clip the ROI to the image, perhaps getting a new ROI
        todraw = self.clipToImage(img)
        if todraw is not None:
            if drawBox:
                todraw.drawBB(img, self.colour)
                todraw.drawText(img, self.colour)  # drawBox will also draw the text (usually)

            # draw into an RGB image
            # first, get the slice into the real image
            if (bb := todraw.bb()) is not None:
                x, y, x2, y2 = bb.corners()
                imgslice = img[y:y2, x:x2]

                # now get the mask and run sobel edge-detection on it if required
                mask = todraw.mask()
                if drawEdge:
                    sx = ndimage.sobel(mask, axis=0, mode='constant')
                    sy = ndimage.sobel(mask, axis=1, mode='constant')
                    mask = np.hypot(sx, sy)

                # flatten and repeat each element of the mask for each channel
                x = np.repeat(np.ravel(mask), 3)
                # and reshape into the same shape as the image slice
                x = np.reshape(x, imgslice.shape)

                # write a colour
                np.putmask(imgslice, x, todraw.colour)

    def draw(self, img):
        self.baseDraw(img)

    def drawBB(self, rgb: 'ImageCube', col):
        """draw BB onto existing RGB image"""
        # write on it - but we MUST WRITE OUTSIDE THE BOUNDS, otherwise we interfere
        # with the image! Doing this predictably with the thickness function
        # in cv.rectangle is a pain, so I'm doing it by hand.
        if (bb := self.bb()) is not None:
            x, y, x2, y2 = bb.corners()
            for i in range(self.fontline):
                cv.rectangle(rgb, (x - i - 1, y - i - 1), (x2 + i, y2 + i), col, thickness=1)

    def drawText(self, rgb: 'ImageCube', col, label=None):
        if (bb := self.bb()) is not None:
            x, y, x2, y2 = bb.corners()
            ty = y if self.labeltop else y2
            if self.fontsize > 0:
                if label is None:
                    label = self.label
                if self.drawbg:
                    # dark text has a white background; light text has a black background
                    bg = (1, 1, 1) if sum(col) < 1.5 else (0, 0, 0)
                else:
                    bg = None
                text.write(rgb,
                           "NO ANNOTATION" if label is None or label == '' else label,
                           x, ty, self.labeltop, self.fontsize, self.fontline, col,
                           bg=bg)

    def serialise(self):
        if self.tpname == 'tmp':
            raise Exception("attempt to serialise a temporary ROI")
        return serialiseFields(self, ROISERIALISEFIELDS)

    def deserialise(self, d):
        deserialiseFields(self, d, ROISERIALISEFIELDS)

    @staticmethod
    def roiUnion(rois):
        bbs = [r.bb() for r in rois]  # get bbs
        bbs = [b for b in bbs if b is not None]
        if len(bbs) > 0:
            x1 = min([b.x for b in bbs])
            y1 = min([b.y for b in bbs])
            x2 = max([b.x + b.w for b in bbs])
            y2 = max([b.y + b.h for b in bbs])
            bb = Rect(x1, y1, x2 - x1, y2 - y1)
            # now construct the mask, initially all False
            mask = np.full((y2 - y1, x2 - x1), False)
            # and OR the ROIs into it
            for r in rois:
                rx, ry, rw, rh = r.bb()
                # calculate ROI's position inside subimage
                x = rx - x1
                y = ry - y1
                # get ROI's mask
                roimask = r.mask()
                # add it at that position
                mask[y:y + rh, x:x + rw] |= roimask
            return ROI('tmp', bb, mask)  # should not be saved
        else:
            # return a null ROI
            return None
            # return ROI(Rect(0, 0, 10, 10), np.full((10, 10), False))

    @staticmethod
    def roiIntersection(rois):
        bbs = [r.bb() for r in rois]  # get bbs
        x1 = min([b.x for b in bbs])
        y1 = min([b.y for b in bbs])
        x2 = max([b.x + b.w for b in bbs])
        y2 = max([b.y + b.h for b in bbs])
        bb = Rect(x1, y1, x2 - x1, y2 - y1)
        # now construct the mask, initially all True
        mask = np.full((y2 - y1, x2 - x1), True)
        # and AND the ROIs into it
        for r in rois:
            rx, ry, rw, rh = r.bb()
            # calculate ROI's position inside subimage
            x = rx - x1
            y = ry - y1
            # get ROI's mask
            roimask = r.mask()
            # construct a working mask, same size as our final mask. We need to do this so that
            # the AND operation goes over the entire result mask.
            workMask = np.full((y2 - y1, x2 - x1), False)
            # add the ROI to the working mask at that position
            workMask[y:y + rh, x:x + rw] = roimask
            # and AND the mask by the work mask.
            mask &= workMask
        return ROI('tmp', bb, mask)

    def clipToImage(self, img: ndarray):
        # clip the ROI to the image. If it doesn't require clipping, just returns the ROI. If it does,
        # returns a new basic ROI. Best not use this for standard drawing, unless you're using the basic
        # draw method anyway, because you'll lose the points and other nuances. Returns None if there is
        # no BB (i.e. the ROI hasn't been set to anything).
        bb = self.bb()
        if bb is not None:
            h, w = img.shape[:2]
            intersect = bb.intersection(Rect(0, 0, w, h))
            if intersect is None:
                raise ROIBoundsException()
            if intersect == bb:
                return self  # intersect of BB with image is same size as BB, so image completely contains ROI.
            # calculate the top left of the part of the mask we are going to copy
            maskX = -bb.x if bb.x < 0 else 0
            maskY = -bb.y if bb.y < 0 else 0
            # and make the new mask
            mask = self.mask()[maskY:maskY + intersect.h, maskX:maskX + intersect.w]
            # construct the ROI.
            return ROI('tmp', intersect, mask)  # should never be saved
        else:
            return None

    def __add__(self, other):
        return self.roiUnion([self, other])

    def __sub__(self, other):
        # the two ROIs overlap, so our resulting ROI will be the same size as the union of both.
        # Wasteful but easy.
        bbs = [r.bb() for r in (self, other)]  # get bbs
        x1 = min([b.x for b in bbs])
        y1 = min([b.y for b in bbs])
        x2 = max([b.x + b.w for b in bbs])
        y2 = max([b.y + b.h for b in bbs])
        bb = Rect(x1, y1, x2 - x1, y2 - y1)
        # now construct the mask, initially all False
        mask = np.full((y2 - y1, x2 - x1), False)

        # Then OR the LHS into the mask
        rx, ry, rw, rh = self.bb()
        # calculate ROI's position inside subimage
        x = rx - x1
        y = ry - y1
        # get ROI's mask
        roimask = self.mask()
        # add it at that position
        mask[y:y + rh, x:x + rw] |= roimask

        # and AND the RHS out of the mask
        rx, ry, rw, rh = other.bb()
        x = rx - x1
        y = ry - y1
        roimask = other.mask()
        workMask = np.full((y2 - y1, x2 - x1), False)
        workMask[y:y + rh, x:x + rw] = roimask
        mask &= ~workMask

        return ROI('tmp', bb, mask)

    def __mul__(self, other):
        return self.roiIntersection([self, other])

    def __truediv__(self, other):
        raise BadOpException()

    def __pow__(self, power, modulo=None):
        raise BadOpException()

    def __str__(self):
        if not self.bb():
            return "ROI-BASE (no data)"
        else:
            x, y, w, h = self.bb()
            return "ROI-BASE {} {} {}x{}".format(x, y, w, h)

    def getSources(self):
        return self.sources


## a rectangle ROI

class ROIRect(ROI):
    def __init__(self):
        super().__init__('rect')
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0
        self.isSet = False
        self.colour = (1, 1, 0)  # annotation colour
        self.fontline = 2
        self.fontsize = 10

    def bb(self):
        if self.isSet:
            return Rect(self.x, self.y, self.w, self.h)
        else:
            return None

    def details(self):
        """Information string on this ROI."""
        if self.x is None:
            return "No ROI"
        else:
            return "{} pixels\n{},{}\n{}x{}".format(self.pixels(),
                                                    self.x, self.y, self.w, self.h)

    def annotate(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        """Simpler version of annotate for rects; doesn't draw the mask"""
        self.annotateBB(p, scale, mapcoords)
        self.annotateText(p, scale, mapcoords)

    def draw(self, img: np.ndarray):
        return  # DISABLED
        self.drawBB(img, self.colour)
        self.drawText(img, self.colour)

    def mask(self):
        # return a boolean array of True, same size as BB
        return np.full((self.h, self.w), True)

    def set(self, x, y, w, h):
        self.isSet = True
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def serialise(self):
        d = super().serialise()
        d.update({'bb': (self.x, self.y, self.w, self.h)})
        d['isset'] = self.isSet
        return d

    def deserialise(self, d):
        super().deserialise(d)
        self.x, self.y, self.w, self.h = d['bb']
        if 'isset' in d:
            self.isSet = d['isset']
        else:
            self.isSet = self.x >= 0  # legacy

    def __str__(self):
        return "ROI-RECT {} {} {}x{}".format(self.x, self.y, self.w, self.h)


class ROICircle(ROI):
    """A simple circular ROI designed for use with multidot regions"""

    x: int
    y: int
    r: int
    isSet: bool
    drawEdge: bool

    def __init__(self, x=-1, y=0, r=0):
        super().__init__('circle')
        self.set(x, y, r)
        self.colour = (1, 1, 0)  # annotation colour
        self.fontline = 2
        self.fontsize = 10
        self.drawBox = False
        self.drawEdge = False

    def set(self, x, y, r):
        self.x = int(x)  # if this is -ve, isSet will be false.
        self.y = int(y)
        self.r = int(r)
        self.isSet = (x >= 0)

    def get(self):
        if self.isSet:
            return self.x, self.y, self.r
        else:
            return None

    def bb(self):
        if self.isSet:
            return Rect(self.x - self.r, self.y - self.r, self.r * 2 + 1, self.r * 2 + 1)
        else:
            return None

    def mask(self):
        # there are a few ways we can generate a circular
        # mask bounded by the BB. This is one of them, which
        # leverages cv's drawing code.
        m = np.zeros((self.r * 2 + 1, self.r * 2 + 1), dtype=np.uint8)
        cv.circle(m, (self.r, self.r), self.r, 255, -1)
        return m > 0

    def draw(self, img):
        return  # DISABLED
        self.baseDraw(img, drawEdge=self.drawEdge, drawBox=self.drawBox)
        self.drawText(img, self.colour)  # these always show label

    def serialise(self):
        d = super().serialise()
        d.update({'croi': (self.x, self.y, self.r, self.isSet, self.drawBox, self.drawEdge)})
        return d

    def deserialise(self, d):
        super().deserialise(d)
        self.drawEdge = False
        self.drawBox = False
        # lot of legacy files causing hackery here.
        if len(d['croi']) == 3:
            self.x, self.y, self.r = d['croi']
            self.isSet = (self.x >= 0)  # legacy
        elif len(d['croi']) == 4:
            self.x, self.y, self.r, self.isSet = d['croi']
        else:
            self.x, self.y, self.r, self.isSet, self.drawBox, self.drawEdge = d['croi']

    def __str__(self):
        return "ROI-CIRCLE {} {} {}".format(self.x, self.y, self.r)


# used in ROIpainted to convert a 0-99 value into a brush size for painting
def getRadiusFromSlider(sliderVal, imgw, imgh, scale=1.0):
    v = max(imgw, imgh)
    return (v / 400) * sliderVal * scale


## a "painted" ROI

class ROIPainted(ROI):
    # we can create this ab initio or from a subimage mask of an image.
    def __init__(self, mask=None, label=None):
        super().__init__('painted')
        self.label = label
        if mask is None:
            self.bbrect = None
            self.map = None
            self.imgw = None
            self.imgh = None
        else:
            h, w = mask.shape[:2]
            self.imgw = w
            self.imgh = h
            self.bbrect = Rect(0, 0, w, h)
            self.map = np.zeros((h, w), dtype=np.uint8)
            self.map[mask] = 255
        self.drawEdge = True
        self.drawBox = True

    def clear(self):
        self.map = None
        self.bbrect = None

    def draw(self, img):
        """Draw the ROI onto an rgb image"""
        return  # DISABLED
        self.baseDraw(img, self.drawBox, self.drawEdge)

    def setImageSize(self, imgw, imgh):
        if self.imgw is not None:
            if self.imgw != imgw or self.imgh != imgh:
                self.clear()

        self.imgw = imgw
        self.imgh = imgh

    def bb(self):
        return self.bbrect

    def centroid(self):
        """Simple centroid from BB"""
        x, y, w, h = self.bbrect
        return x + w / 2, y + h / 2

    def serialise(self):
        d = super().serialise()
        d['bbrect'] = self.bbrect.astuple() if self.bbrect else None
        return serialiseFields(self, ['map'], d=d)

    def deserialise(self, d):
        super().deserialise(d)
        self.bbrect = Rect.fromtuple(d['bbrect'])
        deserialiseFields(self, d, ['map'])

    def mask(self):
        """return a boolean array, same size as BB"""
        return self.map > 0

    def cropDownWithDraw(self, draw=None):
        """crop ROI mask down to smallest possible size and reset BB. If draw is
        set, this will be a function taking the full size image used to draw on
        the ROI as part of the process."""

        # create full size map
        fullsize = np.zeros((self.imgh, self.imgw), dtype=np.uint8)
        # splice in existing data, if there is any!
        if self.bbrect is not None:
            bbx, bby, bbx2, bby2 = self.bbrect.corners()
            fullsize[bby:bby2, bbx:bbx2] = self.map
        if draw is not None:
            # do extra drawing
            draw(fullsize)
        # calculate new bounding box
        cols = np.any(fullsize, axis=0)
        rows = np.any(fullsize, axis=1)
        if cols.any():
            ymin, ymax = np.where(rows)[0][[0, -1]]
            xmin, xmax = np.where(cols)[0][[0, -1]]
            xmax += 1
            ymax += 1
            # cut out the new data
            self.map = fullsize[ymin:ymax, xmin:xmax]
            # construct the new BB
            self.bbrect = Rect(int(xmin), int(ymin), int(xmax - xmin), int(ymax - ymin))
        else:
            self.bbrect = None
            self.map = None

    @staticmethod
    def drawBrush(fullsize, x, y, brushSize, slf, delete):
        """called from inside cropDown as an optional step to draw an extra circle"""
        r = int(getRadiusFromSlider(brushSize, slf.imgw, slf.imgh))
        cv.circle(fullsize, (x, y), r, 0 if delete else 255, -1)

    def setCircle(self, x, y, brushSize, delete=False):
        """fill a circle in the ROI, or clear it (if delete is true)"""
        if self.imgw is not None:
            self.cropDownWithDraw(draw=lambda fullsize: ROIPainted.drawBrush(fullsize, x, y, brushSize, self, delete))

    def __str__(self):
        if not self.bbrect:
            return "ROI-PAINTED (no points)"
        else:
            x, y, w, h = self.bb()
            return "ROI-PAINTED {} {} {}x{}".format(x, y, w, h)


## a polygon ROI

class ROIPoly(ROI):
    def __init__(self):
        super().__init__('poly')
        self.imgw = None
        self.imgh = None
        self.points = []
        self.selectedPoint = None
        self.drawPoints = True
        self.drawBox = True

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

        return Rect(xmin, ymin, xmax - xmin + 1, ymax - ymin + 1)

    def serialise(self):
        d = super().serialise()
        return serialiseFields(self, ['points'], d=d)

    def deserialise(self, d):
        super().deserialise(d)
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

    def annotatePoly(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        """draw the polygon as annotation onto a painter"""

        if len(self.points)>0:
            p.setBrush(Qt.NoBrush)
            p.setPen(rgb2qcol(self.colour))

            # map the into painter coords
            points = [mapcoords(x, y) for (x, y) in self.points]

            # first draw the points as little circles
            if self.drawPoints:
                for (x, y) in points:
                    p.drawEllipse(QPointF(x, y), 5, 5)

            # then the selected point, correcting if it's gone out of range
            # this is drawn as a bigger ring around the point
            if self.selectedPoint is not None:
                if self.selectedPoint >= len(self.points):
                    self.selectedPoint = None
                else:
                    x, y = points[self.selectedPoint]
                    p.drawEllipse(QPointF(x, y), 8, 8)

            # then as a polyline
            points.append(points[0])  # close the loop
            p.drawPolyline([QPointF(x, y) for (x, y) in points])

    def annotate(self, p: QPainter, scale: float, mapcoords: Callable[[float, float], Tuple[float, float]]):
        self.annotatePoly(p, scale, mapcoords)
        self.annotateBB(p, scale, mapcoords)
        self.annotateText(p, scale, mapcoords)

    def draw(self, img):
        return  # DISABLED
        if self.drawBox:
            self.drawBB(img, self.colour)
            self.drawText(img, self.colour)

        # first write the points in the actual image
        if self.drawPoints:
            for p in self.points:
                cv.circle(img, p, 7, self.colour, self.fontline)

        if self.selectedPoint is not None:
            if self.selectedPoint >= len(self.points):
                self.selectedPoint = None
            else:
                p = self.points[self.selectedPoint]
                cv.circle(img, p, 10, self.colour, self.fontline + 1)

        if not self.hasPoly():
            return

        # draw the polygon
        pts = np.array(self.points, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv.polylines(img, [pts], True, self.colour, thickness=self.fontline)

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


def deserialise(self, tp, d):
    """Not to be confused with ROI.deserialise(). This deserialises an serialised ROI datum given its type"""
    if tp == 'rect':
        return ROIRect.deserialise(d)
    elif tp == 'circle':
        return ROICircle.deserialise(d)
    elif tp == 'painted':
        return ROIPainted.deserialise(d)
    elif tp == 'poly':
        return ROIPoly.deserialise(d)
    else:
        raise Exception(f"cannot deserialise ROI type '{tp}'")
