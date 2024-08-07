import copy
from numbers import Number
from typing import Tuple, Optional, Any

import cv2 as cv
import numpy as np
from PySide2.QtCore import Qt, QPointF
from PySide2.QtGui import QPainter, QImage, QPen
from numpy import ndarray
from scipy import ndimage

import pcot.sources
from pcot.sources import SourcesObtainable, nullSourceSet
from pcot.ui.roiedit import RectEditor, CircleEditor, PaintedEditor, PolyEditor
from pcot.utils import serialiseFields, deserialiseFields
from pcot.utils.annotations import Annotation, annotDrawText
from pcot.utils.colour import rgb2qcol
from pcot.utils.flood import FastFloodFiller, FloodFillParams
from pcot.utils.geom import Rect
from pcot.utils.taggedaggregates import TaggedDictType, taggedColourType, TaggedDict, taggedRectType, TaggedTuple, \
    TaggedTupleType, Maybe, TaggedListType

# used as the basic default rectangle for ROIs
rectType = taggedRectType(0, 0, 0, 0)


class BadOpException(Exception):
    def __init__(self):
        super().__init__("op not valid")


class BadNegException(Exception):
    """This gets thrown when you're trying to negate an ROI that has lost its dimensions, which can happen when
    ROIs from different images are combined or they've simply not been added by an operation."""

    def __init__(self):
        super().__init__("Can only negate ROIs with image dimensions")


class ROIBoundsException(Exception):
    def __init__(self):
        super().__init__(
            "ROI is out of bounds or entirely outside image. Have you loaded a new image?")


# These are the fields that make up the common basis of ROIs, as they could
# be passed into a TaggedDictType constructor. We add to these fields for each
# ROI.

ROICOLOURTYPE = taggedColourType(1, 0, 0)

BASEROIFIELDS = [
    ("type", ("type", str, "")),
    ("label", ("label", Maybe(str), "")),
    ("labeltop", ("label on top?", bool, False)),
    ("colour", ("colour", ROICOLOURTYPE)),
    ("thickness", ("thickness", Number, 0)),
    ("fontsize", ("fontsize", Number, 10)),
    ("drawbg", ("draw background", bool, True)),
    ("drawBox", ("draw box", bool, True)),
    ("drawEdge", ("draw edge", bool, True)),
]


class ROI(SourcesObtainable, Annotation):
    """definition of base type for regions of interest - this is useful in itself
    because it defines an ROI consisting of a predefined BB and mask."""

    tpname = None
    roiTypes = {}
    count = 0

    def __init_subclass__(cls, **kwargs):
        """This is called when a subclass is created. It's used to associate the type name with the class"""
        super().__init_subclass__(**kwargs)
        ROI.roiTypes[cls.tpname] = cls

    def __init__(self, bbrect: Rect = None, maskimg: np.array = None,
                 sourceROI=None, isTemp=False, containingImageDimensions=None,
                 label=None):
        """Constructor. Takes an ROI type name, optional rect and mask (for 'base' ROIs consisting of just these)
        and an optional sourceROI from which some data is copied, for copy operations"""

        Annotation.__init__(self)
        SourcesObtainable.__init__(self)

        self.bbrect = bbrect
        self.maskimg = maskimg
        self.internalIdx = ROI.count  # debugging
        ROI.count += 1

        self.isTemp = isTemp  # for temporary ROIs created by expressions

        if label is None:
            self.label = None if sourceROI is None else sourceROI.label
        else:
            self.label = label
        self.labeltop = False if sourceROI is None else sourceROI.labeltop  # draw the label at the top?
        self.colour = (1, 1, 0) if sourceROI is None else sourceROI.colour  # annotation colour
        self.thickness = 0 if sourceROI is None else sourceROI.thickness  # thickness of lines
        self.fontsize = 10 if sourceROI is None else sourceROI.fontsize  # annotation font size
        self.drawbg = True if sourceROI is None else sourceROI.drawbg
        self.drawEdge = True if sourceROI is None else sourceROI.drawEdge  # draw the edge only?
        self.drawBox = True if sourceROI is None else sourceROI.drawBox  # draw the box?
        # by default, the source of an ROI is null.
        # The only time this might not be true is if the ROI is derived somehow from an actual data source.
        self.sources = nullSourceSet if sourceROI is None else sourceROI.sources
        # Usually None, but set when we are creating ROIs in a roiexpr node - or
        # propagating them down in operations (see Intersection and Union ops below)
        self.containingImageDimensions = containingImageDimensions

    def setContainingImageDimensions(self, w, h):
        """This is used when in a roiexpr node - we set the size of the containing image so that we can subtract
        from a rect of that size when negating. Note that we do this in Painted too - that has its own copy."""
        self.containingImageDimensions = (w, h)

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

    def setPen(self, p: QPainter, alpha):
        pen = QPen(rgb2qcol(self.colour, alpha=alpha))
        pen.setWidth(self.thickness)
        p.setPen(pen)

    def annotateBB(self, p: QPainter, alpha):
        """Draw the BB onto a QPainter"""
        if (bb := self.bb()) is not None:
            x, y, w, h = bb.astuple()
            p.setBrush(Qt.NoBrush)
            self.setPen(p, alpha)
            p.drawRect(x, y, w, h)

    def annotateMask(self, p: QPainter, alpha):
        """This is the 'default' annotate, which draws the ROI onto the painter by
        using its actual mask. It takes the mask, edge detects (if drawEdge), converts into
        an image."""
        if (bb := self.bb()) is not None:
            # now get the mask
            mask = self.mask()
            # run sobel edge-detection on it if required
            if self.drawEdge:
                sx = ndimage.sobel(mask, axis=0, mode='constant')
                sy = ndimage.sobel(mask, axis=1, mode='constant')
                mask = np.hypot(sx, sy)
            mask = mask.clip(max=1.0).astype(np.float32)
            # mask = skimage.morphology.erosion(mask)
            ww = int(bb.w)
            hh = int(bb.h)
            mask = cv.resize(mask, dsize=(ww, hh), interpolation=cv.INTER_AREA)
            # now prepare the actual image, which is just a coloured fill rectangle - we
            # will add the mask as an alpha
            img = np.full((hh, ww, 3), self.colour, dtype=np.float32)  # the second arg is the colour
            # add the mask as the alpha channel
            x = np.dstack((img, mask))
            # to byte, taking into account the alpha
            x = (x * 255 * alpha).astype(np.ubyte)
            # resize to canvas/painter scale
            # to qimage, stashing the data into a field to avoid the problem
            # discussed in canvas.img2qimage where memory is freed by accident in Qt
            # (https://bugreports.qt.io/browse/PYSIDE-1563)
            self.workaround = x
            q = QImage(x.data, ww, hh, ww * 4, QImage.Format_RGBA8888)
            # now we have a QImage we can draw it onto the painter.
            p.drawImage(bb.x, bb.y, q)

    def annotateText(self, p: QPainter, alpha):
        """Draw the text for the ROI onto the painter"""
        if (bb := self.bb()) is not None and self.fontsize > 0 and self.label is not None and self.label != '':
            x, y, x2, y2 = bb.corners()
            ty = y if self.labeltop else y2

            annotDrawText(p, x, ty, self.label, self.colour, alpha,
                          basetop=self.labeltop,
                          bgcol=(0, 0, 0) if self.drawbg else None,
                          fontsize=self.fontsize)

    def annotate(self, p: QPainter, img, alpha):
        """This is the default annotation method drawing the ROI onto a QPainter as part of the annotations system.
        It should be replaced with a more specialised method if possible."""
        if self.drawBox:
            self.annotateBB(p, alpha)
        self.annotateText(p, alpha)
        self.annotateMask(p, alpha)

    def to_tagged_dict_common(self, td: TaggedDict):
        """Serialises the common parts of an ROI to am existing TaggedDict. Parts
        that are specific to particular kinds of ROI are handled in that type,
        along with creating the TD in the first place."""
        if self.isTemp:
            raise Exception("attempt to serialise a temporary ROI")

        td.label = self.label
        td.labeltop = self.labeltop
        td.colour = ROICOLOURTYPE.create().set(*self.colour)
        td.thickness = self.thickness
        td.fontsize = self.fontsize
        td.drawbg = self.drawbg
        td.drawBox = self.drawBox
        td.drawEdge = self.drawEdge

        # we also need to add the type
        td.type = self.__class__.tpname
        return td

    def from_tagged_dict_common(self, td: TaggedDict):
        """Deserialise the common parts of an ROI from an existing TaggedDict."""
        # deserialise the common data
        self.label = td.label
        self.labeltop = td.labeltop
        self.colour = td.colour.get()
        self.thickness = td.thickness
        self.fontsize = td.fontsize
        self.drawbg = td.drawbg
        self.drawBox = td.drawBox
        self.drawEdge = td.drawEdge

    @staticmethod
    def new_from_tagged_dict(td: TaggedDict):
        """Creates a new ROI from a tagged dict. This is used for loading from file or memory and creates
        a new ROI. It inspects the dict to find the type of ROI to create."""
        if not isinstance(td, TaggedDict):
            raise Exception("ROI fromSerialised: not a TaggedDict")
        if 'type' not in td:
            raise Exception("ROI fromSerialised: no type field")
        # get the constructor for the ROI type and construct an instance
        constructor = ROI.roiTypes[td['type']]
        r = constructor()
        r.from_tagged_dict(td)
        return r

    @staticmethod
    def fromSerialised(d):
        """Generate from JSON-serialised data with a type field; it's like new_from_tagged_dict
        except it works on a plain JSON-serialisable dict"""
        constructor = ROI.roiTypes[d['type']]
        r = constructor()
        r.deserialise(d)
        return r

    def to_tagged_dict(self) -> TaggedDict:
        """Store the ROI in a tagged dict, whose type (i.e. TaggedDictType) is
        specific to that ROI. Overriden in each subtype."""
        pass

    def from_tagged_dict(self, td: TaggedDict):
        """Set the ROI from the state stored in the TaggedDict, which must be of
        the correct TaggedDictType"""
        pass

    def serialise(self):
        """Convert to JSON-serialisable data via a TaggedDict"""
        td = self.to_tagged_dict()
        return td.serialise()

    def deserialise(self, d):
        """Convert from JSON-serialisable data to a TaggedDict of the correct
        type, and then initialise from that data. Very unlikely we'll call
        this directly but it's here for completeness"""
        # the subclass must have one of these!
        td = self.TAGGEDDICT.deserialise(d)
        self.from_tagged_dict(td)





    @staticmethod
    def roiUnion(rois):
        bbs = [r.bb() for r in rois]  # get bbs
        bbs = [b for b in bbs if b is not None]
        # we set the image dimensions to the last one we got - if they aren't
        # all the same we probably have bigger problems.
        dims = None
        dimsOK = True  # flag to indicate that containing dimensions agree. Attach to result.
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
                if (bb2 := r.bb()) is not None:  # ignore undefined ROIs
                    # here we make sure that the containing image dimensions agree and are propagated
                    # to the result. If they don't agree we zero them.
                    if r.containingImageDimensions is not None:
                        if dims is None:
                            dims = r.containingImageDimensions
                        elif dims != r.containingImageDimensions:
                            dimsOK = False

                    rx, ry, rw, rh = bb2
                    # calculate ROI's position inside subimage
                    x = rx - x1
                    y = ry - y1
                    # get ROI's mask
                    roimask = r.mask()
                    # add it at that position
                    mask[y:y + rh, x:x + rw] |= roimask
            # should not be saved
            roi = ROI(bb, mask, isTemp=True, containingImageDimensions=dims if dimsOK else None)
            roi.sources = pcot.sources.SourceSet(rois)  # can pass list of SourcesObtainable to ctor
            return roi
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
        # we set the image dimensions to the last one we got - if they aren't
        # all the same we probably have bigger problems.
        dims = None
        dimsOK = True
        # and AND the ROIs into it
        for r in rois:
            # here we make sure that the containing image dimensions agree and are propagated
            # to the result. If they don't agree we zero them.
            if r.containingImageDimensions is not None:
                if dims is None:
                    dims = r.containingImageDimensions
                elif dims != r.containingImageDimensions:
                    dimsOK = False
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
        return ROI(bb, mask, isTemp=True, containingImageDimensions=dims if dimsOK else None)

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
            r = ROI(intersect, mask, isTemp=True)  # should never be saved
            # and we can set these, because we know the size of the image
            r.setContainingImageDimensions(w, h)
            return r
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

        # containing dimensions - either one or the other is OK, if both are present they
        # must match.

        if self.containingImageDimensions is None or other.containingImageDimensions is None:
            dims = other.containingImageDimensions if self.containingImageDimensions is None else self.containingImageDimensions
        else:
            dims = self.containingImageDimensions if self.containingImageDimensions == other.containingImageDimensions else None

        return ROI(bb, mask, isTemp=True, containingImageDimensions=dims)

    def getSize(self):
        """return the size of the serialised ROI in bytes, or zero if it's negligible."""
        if self.isTemp:
            raise Exception("attempt to get size of a temporary ROI")
        else:
            return 0

    def __contains__(self, xyTuple):
        """Is a point inside the ROI?"""
        x, y = xyTuple
        if self.bb() is None:
            return False
        else:
            # first check the bounding box
            if xyTuple not in self.bb():
                return False
            # now check the mask
            rx, ry, rw, rh = self.bb()
            x -= rx
            y -= ry
            return self.mask()[y, x]

    def __neg__(self):
        """We can negate an ROI by subtracting it from an ROI set to the entire image - but only
        if we know how big it is!"""
        if self.containingImageDimensions is None:
            raise BadNegException()
        else:
            w, h = self.containingImageDimensions
            r = ROIRect()
            r.set(0, 0, w, h)

            return r - self

    def equals(self, other, sameType=False):
        """Check for equality of two ROIs. I'm not using the dunder method because I want to have an extra
        argument to check if the types are the same."""
        if not isinstance(other, ROI):
            return False
        elif self is other:
            return True
        elif sameType and type(self) != type(other):
            return False
        return self.bb() == other.bb() and np.array_equal(self.mask(), other.mask())

    def __mul__(self, other):
        return self.roiIntersection([self, other])

    def __truediv__(self, other):
        raise BadOpException()

    def __pow__(self, power, modulo=None):
        raise BadOpException()

    def _str(self, use_id):
        lab = "(no label)" if self.label is None else self.label
        s = f"ROI-BASE{self.internalIdx}" if use_id else "ROI-BASE"
        if not self.bb():
            return f"{s}:{lab} (no data)"
        else:
            x, y, w, h = self.bb()
            return f"{s}:{lab} {x} {y} {w}x{h}"

    def __str__(self):
        return self._str(False)

    def __repr__(self):
        return self._str(True)

    def getSources(self):
        return self.sources

    def rebase(self, x, y):
        """move the ROI by -x, -y: effectively moving it from an image into a subset of that image starting at (x,y)"""
        pass

    def createEditor(self, tab):
        """Create an editor for the ROI"""
        pass

    def changed(self):
        """Notify the ROI that its values have been set. This may not actually do anything, but for ROIs like
        Rect and Circle it's necessary. Other ROIs have different ways of knowing if they have a valid value."""
        pass

    def copy(self):
        """Create a copy of the ROI - here for completeness; it's more pythonic to use copy.copy() or copy.deepcopy()"""
        return copy.copy(self)


class ROIRect(ROI):
    """Rectangular ROI"""
    tpname = "rect"
    # build the tagged dict structure we use for serialising rects - it's a tagged dict with the fields
    # of a rect, plus the base ROI fields.
    TAGGEDDICTDEFINITION = BASEROIFIELDS + [
        ('bb', ('rectangle', rectType)),
        ('isset', ('is rectangle set? (internal)', bool, False))]

    TAGGEDDICT = TaggedDictType(*TAGGEDDICTDEFINITION)

    def __init__(self, sourceROI=None, label=None, rect: Tuple[float, float, float, float] = None):
        """Takes the following forms:
        ROIRect() - empty ROI
        ROIRect(rect=(x,y,w,h)) - ROI with given bounding box
        ROIRect(sourceROI=roi) - copy of ROI
        Can also specify a label with label="""
        super().__init__(sourceROI=sourceROI, label=label)
        if sourceROI is None:
            if rect is None:
                self.x = 0
                self.y = 0
                self.w = 0
                self.h = 0
            else:
                self.x, self.y, self.w, self.h = rect
            self.isSet = False
        else:
            if rect is not None:
                raise ValueError("Can't specify both sourceROI and rect")
            self.x, self.y, self.w, self.h = sourceROI.x, sourceROI.y, sourceROI.w, sourceROI.h
            self.isSet = True

    def bb(self):
        if self.w > 0:
            return Rect(self.x, self.y, self.w, self.h)
        else:
            return None

    def details(self):
        """Information string on this ROI."""
        if self.w < 0:
            return "No ROI"
        else:
            return "{} pixels\n{},{}\n{}x{}".format(self.pixels(),
                                                    self.x, self.y, self.w, self.h)

    def annotate(self, p: QPainter, img, alpha):
        """Simpler version of annotate for rects; doesn't draw the mask"""
        self.annotateBB(p, alpha)
        self.annotateText(p, alpha)

    def mask(self):
        # return a boolean array of True, same size as BB
        return np.full((self.h, self.w), True)

    def set(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.isSet = True

    def changed(self):
        self.isSet = True

    def to_tagged_dict(self):
        td = self.TAGGEDDICT.create()
        super().to_tagged_dict_common(td)
        td.bb = rectType.create()
        td.bb.set(self.x, self.y, self.w, self.h)
        td.isset = self.isSet
        return td

    def from_tagged_dict(self, td):
        super().from_tagged_dict_common(td)
        self.x, self.y, self.w, self.h = td['bb']
        self.isSet = td['isset']

    def __copy__(self):
        r = ROIRect(sourceROI=self)
        return r

    def rebase(self, x, y):
        r = ROIRect(sourceROI=self)
        r.x -= x
        r.y -= y
        return r

    def _str(self, use_id):
        lab = "(no label)" if self.label is None else self.label
        s = f"ROI-RECT{self.internalIdx}" if use_id else "ROI-RECT"
        return f"{s}:{lab} {self.x} {self.y} {self.w}x{self.h}"

    def __str__(self):
        return self._str(False)

    def __repr__(self):
        return self._str(True)

    def createEditor(self, tab):
        return RectEditor(tab)


class ROICircle(ROI):
    """A simple circular ROI designed for use with multidot regions"""
    tpname = "circle"

    x: int
    y: int
    r: int
    isSet: bool

    # the tagged dict structure for serialising circles is a single key - croi (circle ROI) - that
    # holds a tuple defining the circle.
    circleType = TaggedTupleType(x=("Centre x coordinate", Number, 0.0),
                                 y=("Centre y coordinate", Number, 0.0),
                                 r=("Radius", Number, 0.0),
                                 isSet=("Is set? (internal)", bool, False)
                                 )

    TAGGEDDICTDEFINITION = BASEROIFIELDS + [
        ('croi', ('circle definition', circleType))]

    TAGGEDDICT = TaggedDictType(*TAGGEDDICTDEFINITION)

    def __init__(self, x=-1, y=0, r=0, sourceROI=None, label=None):
        super().__init__(sourceROI=sourceROI, label=label)
        if sourceROI is None:
            self.set(x, y, r)
        else:
            self.isSet = sourceROI.isSet
            self.x, self.y, self.r = sourceROI.x, sourceROI.y, sourceROI.r

    def set(self, x, y, r):
        self.x = int(x)  # if this is -ve, isSet will be false.
        self.y = int(y)
        self.r = int(r)
        self.isSet = (x >= 0)

    def changed(self):
        self.isSet = True

    def annotate(self, p: QPainter, img, alpha):
        if (bb := self.bb()) is not None:
            self.annotateBB(p, alpha)
            self.annotateText(p, alpha)
            x, y, w, h = bb.astuple()
            p.setBrush(Qt.NoBrush)
            self.setPen(p, alpha)
            p.drawEllipse(x, y, w, h)

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

    def to_tagged_dict(self):
        td = self.TAGGEDDICT.create()
        super().to_tagged_dict_common(td)
        td.croi = self.circleType.create()
        td.croi.set(self.x, self.y, self.r, self.isSet)
        return td

    def from_tagged_dict(self, td):
        super().from_tagged_dict_common(td)
        t = td.croi
        self.x, self.y, self.r = t.x, t.y, t.r
        self.isSet = t.isSet

    def __copy__(self):
        r = ROICircle(sourceROI=self)
        return r

    def rebase(self, x, y):
        r = ROICircle(sourceROI=self)
        r.x -= x
        r.y -= y
        return r

    def createEditor(self, tab):
        return CircleEditor(tab)

    def __str__(self):
        lab = "(no label)" if self.label is None else self.label
        return f"ROI-CIRCLE:{lab} {self.x} {self.y} {self.r}"

    def __repr__(self):
        lab = "(no label)" if self.label is None else self.label
        return f"ROI-CIRCLE{self.internalIdx}:{lab} {self.x} {self.y} {self.r}"


# used in ROIpainted to convert a 0-99 value into a brush size for painting
def getRadiusFromSlider(sliderVal, imgw, imgh, scale=1.0):
    v = max(imgw, imgh)
    return (v / 400) * sliderVal * scale


class ROIPainted(ROI):
    """A painted ROI, which is essentially just a mask"""
    tpname = "painted"

    bbrect: Optional[Rect]
    map: Optional[np.array]

    TAGGEDDICTDEFINITION = BASEROIFIELDS + [
        ('bbrect', ('bounding box', Maybe(rectType), None)),
        ('map', ('mask', Maybe(ndarray), None)),
        ("r", ('brush radius', Number, 10))
    ]

    TAGGEDDICT = TaggedDictType(*TAGGEDDICTDEFINITION)

    # we can create this ab initio or from a subimage mask of an image.
    def __init__(self, mask=None, label=None, sourceROI=None, containingImageDimensions=None):
        super().__init__(sourceROI=sourceROI, label=label,
                         containingImageDimensions=containingImageDimensions)
        if sourceROI is None:
            if mask is None:
                self.bbrect = None
                self.map = None
            else:
                h, w = mask.shape[:2]
                self.bbrect = Rect(0, 0, w, h)
                self.map = np.zeros((h, w), dtype=np.uint8)
                self.map[mask] = 255
        else:
            self.map = sourceROI.mask()  # not a copy?
            self.bbrect = Rect.copy(sourceROI.bb())
        self.r = 10  # default "circle size" for painting; used in multidot editor

    def clear(self):
        self.map = None
        self.bbrect = None

    def bb(self):
        return self.bbrect

    def centroid(self):
        """Simple centroid from BB"""
        x, y, w, h = self.bbrect
        return x + w / 2, y + h / 2

    def to_tagged_dict(self):
        td = self.TAGGEDDICT.create()
        super().to_tagged_dict_common(td)
        # we can't just do td.bbrect = self.bbrect.astuple(), because td.bbrect is a TaggedTuple and
        # self.bbrect is a Rect. Instead we need to create a TaggedTuple.
        td.bbrect = None if self.bbrect is None else rectType.deserialise(self.bbrect.astuple())
        td.map = self.map
        return td

    def from_tagged_dict(self, td):
        super().from_tagged_dict_common(td)
        self.bbrect = Rect.fromtuple(td.bbrect)
        self.r = td.r
        self.map = td.map

    def mask(self):
        """return a boolean array, same size as BB"""
        return self.map > 0

    def getSize(self):
        return 0 if self.map is None else self.map.nbytes

    def fullsize(self):
        """return the full size mask"""
        imgw, imgh = self.containingImageDimensions
        # create full size map of zeroes
        fullsize = np.zeros((imgh, imgw), dtype=np.uint8)
        # splice in existing data, if there is any!
        if self.bbrect is not None:
            bbx, bby, bbx2, bby2 = self.bbrect.corners()
            fullsize[bby:bby2, bbx:bbx2] = self.map
        return fullsize

    def cropDownWithDraw(self, draw=None):
        """crop ROI mask down to smallest possible size and reset BB. If draw is
        set, this will be a function taking the full size image used to draw on
        the ROI as part of the process."""
        fullsize = self.fullsize()
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
            # We've deleted the whole thing! Just mark it as an unset ROI.
            self.bbrect = None
            self.map = None

    def setCircle(self, x, y, brushSize, delete=False, relativeSize=True):
        """fill a circle in the ROI, or clear it (if delete is true). If relativeSize is true, the
        brush size is relative to the image size, otherwise it is absolute in pixels"""

        if self.containingImageDimensions is not None:
            imgw, imgh = self.containingImageDimensions
            if relativeSize:
                r = int(getRadiusFromSlider(brushSize, imgw, imgh))
            else:
                r = int(brushSize)
            self.cropDownWithDraw(draw=lambda fullsize: cv.circle(fullsize, (x, y), r, 0 if delete else 255, -1))
        # store this so that when we select an ROI in the multidot editor we can set the brush size
        self.r = brushSize

    def fill(self, img, x, y, fillparams=FloodFillParams(), fillerclass=FastFloodFiller):
        """fill the ROI using a flood fill"""
        if self.containingImageDimensions is not None:
            # create filler object
            filler = fillerclass(img, fillparams)
            # create a filled mask
            mask = filler.fill(x, y)
            # combine this with the full size existing mask
            self.cropDownWithDraw(draw=lambda fullsize: np.bitwise_or(fullsize, mask, out=fullsize))

    def rebase(self, x, y):
        r = ROIPainted(sourceROI=self)
        r.bbrect.x -= x
        r.bbrect.y -= y
        return r

    def moveBBTo(self, x, y):
        """move the bounding box to a new position, returning True if the move was OK"""
        imgw, imgh = self.containingImageDimensions
        if x >= 0 and y >= 0 and x + self.bbrect.w < imgw and y + self.bbrect.w < imgh:
            self.bbrect.x = x
            self.bbrect.y = y
            return True
        else:
            return False

    def morph(self, op, iterations=1):
        """Perform a morphological operation on the ROI. The function op should take a
        a binary mask, and return a binary mask. The additional iterations parameter specifies
        how many times to apply the operation."""
        if self.map is not None:
            # get full size image because we need to work on the whole thing
            fullsize = self.fullsize()
            # perform the op
            m = op(fullsize, iterations)
            self.map = m
            self.bbrect = Rect(0, 0, m.shape[1], m.shape[0])
            self.setContainingImageDimensions(fullsize.shape[1], fullsize.shape[0])
            # crop it down
            self.cropDownWithDraw()
        else:
            return None

    def dilated(self, n=1):
        r = ROIPainted(sourceROI=self)
        r.dilate(n)
        return r

    def dilate(self, n=1):
        self.morph(lambda mask, iters: cv.dilate(mask, None, iterations=iters), n)

    def erode(self, n=1):
        self.morph(lambda mask, iters: cv.erode(mask, None, iterations=iters), n)

    def __copy__(self):
        r = ROIPainted(sourceROI=self)
        return r

    def createEditor(self, tab):
        return PaintedEditor(tab)

    def _str(self, use_id):
        lab = "(no label)" if self.label is None else self.label
        s = f"ROI-PAINTED{self.internalIdx}" if use_id else f"ROI-PAINTED:{lab}"
        if self.bbrect:
            x, y, w, h = self.bb()
            s += f" {x} {y} {w}x{h}"
        else:
            s += " (not set)"
        return s

    def __str__(self):
        return self._str(use_id=False)

    def __repr__(self):
        return self._str(use_id=True)


## a polygon ROI

class ROIPoly(ROI):
    tpname = "poly"

    pointType = TaggedTupleType(x=("x", Number, 0.0),
                                y=("y", Number, 0.0))

    listOfPointsType = TaggedListType("list of points", pointType, 0)

    TAGGEDDICTDEFINITION = BASEROIFIELDS + [
        ('points', ('points', listOfPointsType)),
        ('drawPoints', ('draw points', bool, True))]
    TAGGEDDICT = TaggedDictType(*TAGGEDDICTDEFINITION)

    def __init__(self, sourceROI=None, label=None):
        super().__init__(sourceROI=sourceROI, label=label)
        self.selectedPoint = None  # don't set the selected point in copies
        if sourceROI is None:
            self.drawPoints = True
            self.points = []
        else:
            self.drawPoints = sourceROI.drawPoints
            self.points = [(x, y) for x, y in sourceROI.points]  # deep copy

    def clear(self):
        self.points = []
        self.selectedPoint = None

    def hasPoly(self):
        return len(self.points) > 2

    def bb(self):
        if not self.hasPoly():
            return None

        xmin = min([p[0] for p in self.points])
        xmax = max([p[0] for p in self.points])
        ymin = min([p[1] for p in self.points])
        ymax = max([p[1] for p in self.points])

        return Rect(xmin, ymin, xmax - xmin + 1, ymax - ymin + 1)

    def to_tagged_dict(self) -> TaggedDict:
        td = self.TAGGEDDICT.create()
        super().to_tagged_dict_common(td)
        td.points = self.listOfPointsType.create()
        for p in self.points:
            tp = self.pointType.create().set(*p)
            td.points.append(tp)
        td.drawPoints = self.drawPoints
        return td

    def from_tagged_dict(self, td: TaggedDict):
        super().from_tagged_dict_common(td)
        self.points = [p.astuple() for p in td.points]
        self.drawPoints = td.drawPoints

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

    def annotatePoly(self, p: QPainter, alpha):
        """draw the polygon as annotation onto a painter"""

        if len(self.points) > 0:
            p.setBrush(Qt.NoBrush)
            self.setPen(p, alpha=alpha)

            # first draw the points as little circles
            points = self.points.copy()  # we make a copy because we append a temporary later...
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

    def annotate(self, p: QPainter, img, alpha):
        self.annotatePoly(p, alpha)
        if self.drawBox:
            self.annotateBB(p, alpha)
        self.annotateText(p, alpha)

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

    def rebase(self, x, y):
        r = ROIPoly(sourceROI=self)
        r.points = [(xx - x, yy - y) for xx, yy in self.points]
        return r

    def __copy__(self):
        r = ROIPoly(sourceROI=self)
        return r

    def createEditor(self, tab):
        return PolyEditor(tab)

    def _str(self, use_id):
        lab = "(no label)" if self.label is None else self.label
        s = f"ROI-POLY{self.internalIdx}:{lab}" if use_id else f"ROI-POLY:{lab}"
        if not self.hasPoly():
            return s + " (no points)"
        x, y, w, h = self.bb()
        return s + f" {x} {y} {w}x{h}"

    def __str__(self):
        return self._str(use_id=True)

    def __repr__(self):
        return self._str(use_id=False)


def new_from_tagged_dict(tp, td):
    """Not to be confused with ROI.new_from_tagged_dict(). This creates a new ROI from a TaggedDict given its type."""
    # first create the ROI
    if tp == 'rect':
        r = ROIRect()
    elif tp == 'circle':
        r = ROICircle()
    elif tp == 'painted':
        r = ROIPainted()
    elif tp == 'poly':
        r = ROIPoly()
    else:
        raise Exception(f"cannot deserialise ROI type '{tp}'")
    # then construct its data
    r.from_tagged_dict(td)
    return r
