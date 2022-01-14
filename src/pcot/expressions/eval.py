"""This is the application-specific part of the expression parsing system.

Anything in here should be specific to PCOT itself, and all data should be as Datum objects.
"""
from typing import List, Optional, SupportsFloat

import cv2 as cv
import numpy as np

import pcot.config
import pcot.operations as operations
from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot.utils.ops import binop, unop
from pcot.xform import XFormException
from .parse import Parameter, Parser, execute

# TODO: keep expression guide in help updated
from .. import rois
from ..sources import SourceSet, MultiBandSource


def extractChannelByName(a: Datum, b: Datum):
    """Extract a channel by name from an image, used for the $ operator.
    a: a Datum which must be an image
    b: a Datum which must be an identifier or numeric wavelength
    return: a new single-channel image datum
    """
    if a is None or b is None:
        return None

    if a.tp != Datum.IMG:
        raise XFormException('DATA', "channel extract operator '$' requires image LHS")
    img = a.val

    if b.tp == Datum.NUMBER or b.tp == Datum.IDENT:
        img = img.getChannelImageByFilter(b.val)
    else:
        raise XFormException('DATA', "channel extract operator '$' requires ident or numeric wavelength RHS")

    if img is None:
        raise XFormException('EXPR', "unable to get this wavelength from an image: " + str(b))

    img.rois = a.val.rois.copy()
    return Datum(Datum.IMG, img)


def funcMerge(args: List[Datum], optargs):
    """Function for merging a number of images. Crops all images to same size as smallest image."""
    if any([x is None for x in args]):
        raise XFormException('EXPR', 'argument is None for merge')
    if any([not x.isImage() for x in args]):
        raise XFormException('EXPR', 'merge only accepts images')

    args = [x.get(Datum.IMG) for x in args]

    # work out minimum width and height of all images
    w = min([i.w for i in args])
    h = min([i.h for i in args])

    bands = []
    sources = []
    for x in args:
        if x.channels == 1:
            bands.append(x.img[:h, :w])
            print(x.img)
        else:
            bands = bands + cv.split(x.img[:h, :w])
        sources = sources + x.sources.sourceSets

    img = np.stack(bands, axis=-1)
    img = ImageCube(img, None, MultiBandSource(sources))

    return Datum(Datum.IMG, img)


def funcGrey(args, optargs):
    """Greyscale conversion. If the optional second argument is nonzero, and the image has 3 channels, we'll use CV's
    conversion equation rather than just the mean."""

    img = args[0].get(Datum.IMG)
    sources = MultiBandSource([SourceSet(img.sources.getSources())])

    if optargs[0].get(Datum.NUMBER) != 0:
        if img.channels != 3:
            raise XFormException('DATA', "Image must be RGB for OpenCV greyscale conversion")
        img = ImageCube(cv.cvtColor(img.img, cv.COLOR_RGB2GRAY), img.mapping, sources)
    else:
        # create a transformation matrix specifying that the output is a single channel which
        # is the mean of all the channels in the source
        mat = np.array([1 / img.channels] * img.channels).reshape((1, img.channels))
        out = cv.transform(img.img, mat)
        img = ImageCube(out, img.mapping, sources)
    return Datum(Datum.IMG, img)


def funcCrop(args, _):
    img = args[0].get(Datum.IMG)
    x, y, w, h = [int(x.get(Datum.NUMBER)) for x in args[1:]]
    out = img.img[y:y + h, x:x + w]
    img = ImageCube(out, img.mapping, img.sources)
    return Datum(Datum.IMG, img)


def funcROI(args, _):
    """Get ROI from image"""
    img = args[0].get(Datum.IMG)
    if len(img.rois) == 0:
        # No ROIs at all? Make one out of the image.
        roi = rois.ROIRect()
        roi.setBB(0, 0, img.w, img.h)
    elif len(img.rois) == 1:
        # One ROI only? Use that (not a copy).
        roi = img.rois[0]
    else:
        # Some ROIs? Make a new union ROI out of them all
        roi = rois.ROI.roiUnion(img.rois)
    return Datum(Datum.ROI, roi, sources=roi.getSources())


def funcAddROI(args, _):
    """Add ROI to image ROI set"""
    img = args[0].get(Datum.IMG)
    if img is not None:
        roi = args[1].get(Datum.ROI)
        if roi is not None:
            img = img.copy()
            img.rois.append(roi)
        return Datum(Datum.IMG, img)
    else:
        return None


def funcWrapper(fn, d, *args):
    """Wrapper around a evaluator function that deals with ROIs etc.
    compare this with exprWrapper in operations, which only handles images and delegates
    processing ROI stuff to the function."""
    if d is None:
        return None
    elif d.isImage():  # deal with image argument
        img = d.val
        subimage = img.subimage()
        mask = subimage.fullmask()
        cp = subimage.img.copy()
        masked = np.ma.masked_array(cp, mask=~mask)
        newdata = fn(masked, *args)  # the result of this could be *anything*
        # so now we look at the result and build an appropriate Datum
        if isinstance(newdata, np.ndarray):
            np.putmask(cp, mask, newdata)
            img = img.modifyWithSub(subimage, newdata)
            return Datum(Datum.IMG, img)
        elif isinstance(newdata, SupportsFloat):
            # 'img' is SourcesObtainable.
            return Datum(Datum.NUMBER, float(newdata), img)
        else:
            raise XFormException('EXPR', 'internal: fn returns bad type in funcWrapper')
    elif d.tp == Datum.NUMBER:  # deal with numeric argument (always returns a numeric result)
        # get sources for all arguments
        ss = [a.getSources() for a in args]
        ss.append(d.getSources())
        return Datum(Datum.NUMBER, fn(d.val, *args), SourceSet(ss))


def statsWrapper(fn, d: List[Optional[Datum]], *args):
    """similar to funcWrapper, but can take lots of image and number arguments which it aggregates to do stats on.
    The result of fn must be a number. Works by flattening any images and concatenating them with any numbers,
    and doing the operation on the resulting data."""
    intermediate = None
    sources = []
    for x in d:
        # get each datum, which is either numeric or an image.
        if x is None:
            continue
        elif x.isImage():
            # if an image, convert to a 1D array
            subimage = x.val.subimage()
            mask = subimage.fullmask()
            cp = subimage.img.copy()
            sources.append(x.getSources())
            masked = np.ma.masked_array(cp, mask=~mask)
            # we convert the data into a flat numpy array if it isn't one already
            if isinstance(masked, np.ma.masked_array):
                newdata = masked.compressed()  # convert to 1d and remove masked elements
            elif isinstance(masked, np.ndarray):
                newdata = masked.flatten()  # convert to 1d
            else:
                raise XFormException('EXPR', 'internal: fn returns bad type in statsWrapper')
        elif x.tp == Datum.NUMBER:
            # if a number, convert to a single-value array
            newdata = np.array([x.val], np.float32)
            sources.append(x.getSources())
        else:
            raise XFormException('EXPR', 'internal: bad type passed to statsWrapper')

        # and concat it to the intermediate array
        if intermediate is None:
            intermediate = newdata
        else:
            intermediate = np.concatenate((intermediate, newdata))

    # then we perform the function on the collated array
    return Datum(Datum.NUMBER, fn(intermediate, *args), sources)


class ExpressionEvaluator(Parser):
    """The core class for the expression evaluator, based on a generic Parser. The constructor
    is responsible for registering most functions."""

    def __init__(self):
        """Initialise the evaluator, registering functions and operators.
        Caller may add other things (e.g. variables)"""
        super().__init__(True)  # naked identifiers permitted
        self.registerBinop('+', 10, lambda a, b: binop(a, b, lambda x, y: x + y, None))
        self.registerBinop('-', 10, lambda a, b: binop(a, b, lambda x, y: x - y, None))
        self.registerBinop('/', 20, lambda a, b: binop(a, b, lambda x, y: x / y, None))
        self.registerBinop('*', 20, lambda a, b: binop(a, b, lambda x, y: x * y, None))
        self.registerBinop('^', 30, lambda a, b: binop(a, b, lambda x, y: x ** y, None))
        self.registerUnop('-', 50, lambda x: unop(x, lambda a: -a, None))

        # standard fuzzy operators (i.e. Zadeh)
        self.registerBinop('&', 20, lambda a, b: binop(a, b, lambda x, y: np.minimum(x, y), None))
        self.registerBinop('|', 20, lambda a, b: binop(a, b, lambda x, y: np.maximum(x, y), None))
        self.registerUnop('!', 50, lambda x: unop(x, lambda a: 1 - a, None))

        self.registerBinop('$', 100, extractChannelByName)

        # additional functions and properties - this is in the __init__.py in the operations package.
        operations.registerOpFunctionsAndProperties(self)

        self.registerFunc("merge",
                          "merge a number of images into a single image - if the image has multiple channels they will all be merged in.",
                          [Parameter("image", "an image of any depth", Datum.IMG)],
                          [],
                          funcMerge, varargs=True)
        self.registerFunc("sin", "calculate sine of angle in radians",
                          [Parameter("angle", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                          [],
                          lambda args, optargs: funcWrapper(np.sin, args[0]))
        self.registerFunc("cos", "calculate cosine of angle in radians",
                          [Parameter("angle", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                          [],
                          lambda args, optargs: funcWrapper(np.cos, args[0]))
        self.registerFunc("tan", "calculate tangent of angle in radians",
                          [Parameter("angle", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                          [],
                          lambda args, optargs: funcWrapper(np.tan, args[0]))
        self.registerFunc("sqrt", "calculate the square root",
                          [Parameter("angle", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                          [],
                          lambda args, optargs: funcWrapper(np.sqrt, args[0]))

        self.registerFunc("min", "find the minimum value of pixels in a list of ROIs, images or values",
                          [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                          [],
                          lambda args, optargs: statsWrapper(np.min, args), varargs=True)
        self.registerFunc("max", "find the maximum value of pixels in a list of ROIs, images or values",
                          [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                          [],
                          lambda args, optargs: statsWrapper(np.max, args), varargs=True)
        self.registerFunc("sd", "find the standard deviation of pixels in a list of ROIs, images or values",
                          [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                          [],
                          lambda args, optargs: statsWrapper(np.std, args), varargs=True)
        self.registerFunc("mean", "find the standard deviation of pixels in a list of ROIs, images or values",
                          [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                          [],
                          lambda args, optargs: statsWrapper(np.mean, args), varargs=True)

        self.registerFunc("grey", "convert an image to greyscale",
                          [Parameter("image", "an image to process", Datum.IMG)],
                          [Parameter("useCV",
                                     "if non-zero, use openCV greyscale conversion (RGB input only): 0.299*R + 0.587*G + 0.114*B",
                                     Datum.NUMBER, deflt=0)],
                          funcGrey)

        self.registerFunc("crop", "crop an image to a rectangle",
                          [Parameter("image", "an image to process", Datum.IMG),
                           Parameter("x", "x coordinate of top-left corner", Datum.NUMBER),
                           Parameter("y", "y coordinate of top-left corner", Datum.NUMBER),
                           Parameter("w", "width of rectangle", Datum.NUMBER),
                           Parameter("h", "height of rectangle", Datum.NUMBER)],
                          [],
                          funcCrop)

        self.registerFunc("roi", "extract ROI from image (returns rect ROI on entire image if none is present",
                          [Parameter("image", "image to extract ROI from", Datum.IMG)],
                          [],
                          funcROI)

        self.registerFunc("addroi", "add ROI to image",
                          [Parameter("image", "image to add ROI to", Datum.IMG),
                           Parameter("roi", "ROI", Datum.ROI)
                           ],
                          [],
                          funcAddROI)

        self.registerProperty('w', Datum.IMG,
                              "give the width of an image in pixels (if there are ROIs, give the width of the BB of the ROI union)",
                              lambda q: Datum(Datum.NUMBER, q.subimage().bb.w, SourceSet(q.getSources())))
        self.registerProperty('w', Datum.ROI, "give the width of an ROI in pixels",
                              lambda q: Datum(Datum.NUMBER, q.bb().w, SourceSet(q.getSources())))
        self.registerProperty('h', Datum.IMG,
                              "give the height of an image in pixels (if there are ROIs, give the width of the BB of the ROI union)",
                              lambda q: Datum(Datum.NUMBER, q.subimage().bb.h, SourceSet(q.getSources())))
        self.registerProperty('h', Datum.ROI, "give the width of an ROI in pixels",
                              lambda q: Datum(Datum.NUMBER, q.bb().h, SourceSet(q.getSources())))

        self.registerProperty('n', Datum.IMG,
                              "give the area of an image in pixels (if there are ROIs, give the number of pixels in the ROI union)",
                              lambda q: Datum(Datum.NUMBER, q.subimage().mask.sum(), SourceSet(q.getSources())))
        self.registerProperty('n', Datum.ROI, "give the number of pixels in an ROI",
                              lambda q: Datum(Datum.NUMBER, q.pixels(), SourceSet(q.getSources())))

        for x in pcot.config.exprFuncHooks:
            x(self)

    def run(self, s):
        """Parse and evaluate an expression."""
        self.parse(s)

        stack = []
        return execute(self.output, stack)
