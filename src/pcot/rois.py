from collections import namedtuple

import numpy as np
import cv2 as cv
from scipy import ndimage

from pcot.utils import text, serialiseFields, deserialiseFields


class BadOpException(Exception):
    def __init__(self):
        super().__init__("op not valid")


ROISERIALISEFIELDS = ['label', 'labeltop', 'colour', 'fontline', 'fontsize', 'drawbg']


class ROI:
    """definition of base type for regions of interest - this is useful in itself
    because it defines an ROI consisting of a predefined BB and mask."""

    def __init__(self, bbrect=None, maskimg=None):
        """Ctor. ROIs have a label, which is used to label data in nodes like 'spectrum' and appears in annotations"""
        self.label = None
        self.bbrect = bbrect
        self.maskimg = maskimg

        self.labeltop = False  # draw the label at the top?
        self.colour = (1, 1, 0)  # annotation colour
        self.fontline = 2  # thickness of lines and text
        self.fontsize = 10  # annotation font size
        self.drawbg = True

    def setDrawProps(self, labeltop, colour, fontsize, fontline, drawbg):
        """set the common draw properties for all ROIs"""
        self.labeltop = labeltop
        self.colour = colour
        self.fontline = fontline
        self.fontsize = fontsize
        self.drawbg = drawbg


    def bb(self):
        """return a (x,y,w,h) tuple describing the bounding box for this ROI"""
        return self.bbrect

    def crop(self, img):
        """return an image cropped to the BB"""
        x, y, w, h = self.bb()
        return img.img[y:y + h, x:x + w]

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

    def baseDraw(self, img, drawBox=False, drawEdge=True):
        """Draw the ROI onto an RGB image using the set colour (yellow by default)"""
        if drawBox:
            self.drawBB(img, self.colour)
            self.drawText(img, self.colour)  # drawBox will also draw the text (usually)

        # draw into an RGB image
        # first, get the slice into the real image
        if (bb := self.bb()) is not None:
            x, y, w, h = bb
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
            np.putmask(imgslice, x, self.colour)

    def draw(self, img):
        self.baseDraw(img)

    def drawBB(self, rgb: 'ImageCube', col):
        """draw BB onto existing RGB image"""
        # write on it - but we MUST WRITE OUTSIDE THE BOUNDS, otherwise we interfere
        # with the image! Doing this predictably with the thickness function
        # in cv.rectangle is a pain, so I'm doing it by hand.
        if (bb := self.bb()) is not None:
            x, y, w, h = bb
            for i in range(self.fontline):
                cv.rectangle(rgb, (x - i - 1, y - i - 1), (x + w + i, y + h + i), col, thickness=1)

    def drawText(self, rgb: 'ImageCube', col, label=None):
        if (bb := self.bb()) is not None:
            x, y, w, h = bb
            ty = y if self.labeltop else y + h
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
        return serialiseFields(self, ROISERIALISEFIELDS)

    def deserialise(self, d):
        deserialiseFields(self, d, ROISERIALISEFIELDS)

    @staticmethod
    def roiUnion(rois):
        bbs = [r.bb() for r in rois]  # get bbs
        x1 = min([b[0] for b in bbs])
        y1 = min([b[1] for b in bbs])
        x2 = max([b[0] + b[2] for b in bbs])
        y2 = max([b[1] + b[3] for b in bbs])
        bb = (x1, y1, x2 - x1, y2 - y1)
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
        return ROI(bb, mask)

    @staticmethod
    def roiIntersection(rois):
        bbs = [r.bb() for r in rois]  # get bbs
        x1 = min([b[0] for b in bbs])
        y1 = min([b[1] for b in bbs])
        x2 = max([b[0] + b[2] for b in bbs])
        y2 = max([b[1] + b[3] for b in bbs])
        bb = (x1, y1, x2 - x1, y2 - y1)
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
        return ROI(bb, mask)

    def __add__(self, other):
        return self.roiUnion([self, other])

    def __sub__(self, other):
        # the two ROIs overlap, so our resulting ROI will be the same size as the union of both.
        # Wasteful but easy.
        bbs = [r.bb() for r in (self, other)]  # get bbs
        x1 = min([b[0] for b in bbs])
        y1 = min([b[1] for b in bbs])
        x2 = max([b[0] + b[2] for b in bbs])
        y2 = max([b[1] + b[3] for b in bbs])
        bb = (x1, y1, x2 - x1, y2 - y1)
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

        return ROI(bb, mask)

    def __mul__(self, other):
        return self.roiIntersection([self, other])

    def __truediv__(self, other):
        raise BadOpException()

    def __pow__(self, power, modulo=None):
        raise BadOpException()


## a rectangle ROI

class ROIRect(ROI):
    def __init__(self):
        super().__init__()
        self.x = -1
        self.y = 0
        self.w = 0
        self.h = 0
        self.colour = (1, 1, 0)  # annotation colour
        self.fontline = 2
        self.fontsize = 10

    def bb(self):
        if self.x < 0:
            return None
        return self.x, self.y, self.w, self.h

    def draw(self, img: np.ndarray):
        self.drawBB(img, self.colour)
        self.drawText(img, self.colour)

    def mask(self):
        # return a boolean array of True, same size as BB
        return np.full((self.h, self.w), True)

    def setBB(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def serialise(self):
        d = super().serialise()
        d.update({'bb': (self.x, self.y, self.w, self.h)})
        return d

    def deserialise(self, d):
        super().deserialise(d)
        self.x, self.y, self.w, self.h = d['bb']

    def __str__(self):
        return "ROI-RECT {} {} {}x{}".format(self.x, self.y, self.w, self.h)


class ROICircle(ROI):
    """A simple circular ROI designed for use with multidot regions"""

    def __init__(self, x=-1, y=0, r=0):
        super().__init__()
        self.x = x
        self.y = y
        self.r = r
        self.colour = (1, 1, 0)  # annotation colour
        self.fontline = 2
        self.fontsize = 10
        self.drawBox = False

    def bb(self):
        if self.x < 0:
            return None
        return self.x - self.r, self.y - self.r, self.r * 2, self.r * 2

    def mask(self):
        # there are a few ways we can generate a circular
        # mask bounded by the BB. This is one of them, which
        # leverages cv's drawing code.
        m = np.zeros((self.r * 2, self.r * 2), dtype=np.uint8)
        cv.circle(m, (self.r, self.r), self.r, 255, -1)
        return m > 0

    def draw(self, img):
        self.baseDraw(img, drawEdge=False, drawBox=self.drawBox)
        self.drawText(img, self.colour)  # these always show label

    def serialise(self):
        d = super().serialise()
        d.update({'croi': (self.x, self.y, self.r)})
        return d

    def deserialise(self, d):
        super().deserialise(d)
        self.x, self.y, self.r = d['croi']

    def __str__(self):
        return "ROI-CIRCLE {} {} {}".format(self.x, self.y, self.r)


# used in ROIpainted to convert a 0-99 value into a brush size for painting
def getRadiusFromSlider(sliderVal, imgw, imgh, scale=1.0):
    v = max(imgw, imgh)
    return (v / 400) * sliderVal * scale


## a "painted" ROI

class ROIPainted(ROI):
    # we can create this ab initio or from a subimage mask
    def __init__(self, mask=None, label=None):
        super().__init__()
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
            self.bbrect = (0, 0, w, h)
            self.map = np.zeros((h, w), dtype=np.uint8)
            self.map[mask] = 255
        self.drawEdge = True
        self.drawBox = True

    def clear(self):
        self.map = None
        self.bbrect = None

    def draw(self, img):
        """Draw the ROI onto an rgb image"""
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
        return serialiseFields(self, ['bbrect', 'map'], d=d)

    def deserialise(self, d):
        super().deserialise(d)
        deserialiseFields(self, d, ['bbrect', 'map'])

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
            bbx, bby, bbw, bbh = self.bbrect
            fullsize[bby:bby + bbh, bbx:bbx + bbw] = self.map
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
            self.bbrect = (int(xmin), int(ymin), int(xmax - xmin), int(ymax - ymin))
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
        super().__init__()
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

        return xmin, ymin, xmax - xmin, ymax - ymin

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

    def draw(self, img):
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
