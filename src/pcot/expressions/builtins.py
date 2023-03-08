"""
Builtin functions and properties. Needs to be explicitly imported so the decorators run!
"""

from typing import List, SupportsFloat, Optional

import numpy as np

from pcot import rois
from pcot.config import parserhook
from pcot.datum import Datum
from pcot.expressions import Parameter
from pcot.imagecube import ImageCube
from pcot.sources import SourceSet, MultiBandSource
from pcot.utils import image
from pcot.xform import XFormException
import cv2 as cv


def funcMerge(args: List[Datum], optargs):
    """Function for merging a number of images. Crops all images to same size as smallest image."""
    if any([x is None for x in args]):
        raise XFormException('EXPR', 'argument is None for merge')

    if not any([x.isImage() for x in args]):
        raise XFormException('EXPR', 'merge must take at least one image')

    # check sizes of all images are the same
    imgargs = [x.get(Datum.IMG) for x in args if x.isImage()]
    if len(set([(i.w, i.h) for i in imgargs])) != 1:
        raise XFormException('EXPR', 'all images in merge must be the same size')
    # get image size
    w = imgargs[0].w
    h = imgargs[0].h

    # convert numeric values to 1-channel images of that size
    imglist = []
    for x in args:
        if x.isImage():
            imglist.append(x.val)
        elif x.tp == Datum.NUMBER:
            dat = np.full((h, w), x.val, dtype=np.float32)
            imglist.append(ImageCube(dat, None, None))
        else:
            raise XFormException('EXPR', 'arguments to merge must be images or numbers')

    # and merge
    bands = []
    sources = []
    for x in imglist:
        if x.channels == 1:
            bands.append(x.img[:h, :w])
        else:
            bands = bands + image.imgsplit(x.img)
        sources = sources + x.sources.sourceSets

    img = image.imgmerge(bands)
    img = ImageCube(img, None, MultiBandSource(sources))

    return Datum(Datum.IMG, img)


def funcGrey(args, optargs):
    """Greyscale conversion. If the optional second argument is nonzero, and the image has 3 channels, we'll use CV's
    conversion equation rather than just the mean."""

    img = args[0].get(Datum.IMG)

    ss = SourceSet([img.sources, optargs[0].getSources()])
    sources = MultiBandSource([ss])

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
        roi.set(0, 0, img.w, img.h)
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


def funcUncertaintyImage(args, _):
    img = args[0].get(Datum.IMG)
    if img is not None:
        img = ImageCube(img.uncertainty, None, img.sources, rois=img.rois)

    return Datum(Datum.IMG, img)


def funcRGBImage(args, _):
    img = args[0].get(Datum.IMG)
    if img is not None:
        img = img.rgbImage()

    return Datum(Datum.IMG, img)


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
            sources.append(x.sources)
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
            sources.append(x.sources)
        else:
            raise XFormException('EXPR', 'internal: bad type passed to statsWrapper')

        # and concat it to the intermediate array
        if intermediate is None:
            intermediate = newdata
        else:
            intermediate = np.concatenate((intermediate, newdata))

    # then we perform the function on the collated array
    return Datum(Datum.NUMBER, fn(intermediate, *args), SourceSet(sources))


@parserhook
def registerBuiltinFunctions(p):
    p.registerFunc("merge",
                   "merge a number of images into a single image - if the image has multiple channels they will all be merged in.",
                   [Parameter("image", "an image of any depth", (Datum.NUMBER, Datum.IMG))],
                   [],
                   funcMerge, varargs=True)
    p.registerFunc("sin", "calculate sine of angle in radians",
                   [Parameter("angle", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: funcWrapper(np.sin, args[0]))
    p.registerFunc("cos", "calculate cosine of angle in radians",
                   [Parameter("angle", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: funcWrapper(np.cos, args[0]))
    p.registerFunc("tan", "calculate tangent of angle in radians",
                   [Parameter("angle", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: funcWrapper(np.tan, args[0]))
    p.registerFunc("sqrt", "calculate the square root",
                   [Parameter("angle", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: funcWrapper(np.sqrt, args[0]))

    p.registerFunc("min", "find the minimum value of pixels in a list of ROIs, images or values",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.min, args), varargs=True)
    p.registerFunc("max", "find the maximum value of pixels in a list of ROIs, images or values",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.max, args), varargs=True)
    p.registerFunc("sd", "find the standard deviation of pixels in a list of ROIs, images or values",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.std, args), varargs=True)
    p.registerFunc("mean", "find the mean of pixels in a list of ROIs, images or values",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.mean, args), varargs=True)
    p.registerFunc("sum", "find the sum of pixels in a list of ROIs, images or values",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.sum, args), varargs=True)

    p.registerFunc("grey", "convert an image to greyscale",
                   [Parameter("image", "an image to process", Datum.IMG)],
                   [Parameter("useCV",
                              "if non-zero, use openCV greyscale conversion (RGB input only): 0.299*R + 0.587*G + 0.114*B",
                              Datum.NUMBER, deflt=0)],
                   funcGrey)

    p.registerFunc("crop", "crop an image to a rectangle",
                   [Parameter("image", "an image to process", Datum.IMG),
                    Parameter("x", "x coordinate of top-left corner", Datum.NUMBER),
                    Parameter("y", "y coordinate of top-left corner", Datum.NUMBER),
                    Parameter("w", "width of rectangle", Datum.NUMBER),
                    Parameter("h", "height of rectangle", Datum.NUMBER)],
                   [],
                   funcCrop)

    p.registerFunc("roi", "extract ROI from image (returns rect ROI on entire image if none is present",
                   [Parameter("image", "image to extract ROI from", Datum.IMG)],
                   [],
                   funcROI)

    p.registerFunc("addroi", "add ROI to image",
                   [Parameter("image", "image to add ROI to", Datum.IMG),
                    Parameter("roi", "ROI", Datum.ROI)
                    ],
                   [],
                   funcAddROI)

    p.registerFunc(
        "uncertainty",
        "create an image made up of uncertainty data for all channels (or a zero channel if none)",
        [Parameter("image", "the image to process", Datum.IMG)],
        [],
        funcUncertaintyImage
    )

    p.registerFunc(
        "rgb",
        "create a 3-channel image consisting of the current RGB mapping of the input image",
        [Parameter("image", "the image to process", Datum.IMG)],
        [],
        funcRGBImage
    )


@parserhook
def registerBuiltinProperties(p):
    p.registerProperty('w', Datum.IMG,
                       "give the width of an image in pixels (if there are ROIs, give the width of the BB of the ROI union)",
                       lambda q: Datum(Datum.NUMBER, q.subimage().bb.w, SourceSet(q.getSources())))
    p.registerProperty('w', Datum.ROI, "give the width of an ROI in pixels",
                       lambda q: Datum(Datum.NUMBER, q.bb().w, SourceSet(q.getSources())))
    p.registerProperty('h', Datum.IMG,
                       "give the height of an image in pixels (if there are ROIs, give the width of the BB of the ROI union)",
                       lambda q: Datum(Datum.NUMBER, q.subimage().bb.h, SourceSet(q.getSources())))
    p.registerProperty('h', Datum.ROI, "give the width of an ROI in pixels",
                       lambda q: Datum(Datum.NUMBER, q.bb().h, SourceSet(q.getSources())))

    p.registerProperty('n', Datum.IMG,
                       "give the area of an image in pixels (if there are ROIs, give the number of pixels in the ROI union)",
                       lambda q: Datum(Datum.NUMBER, q.subimage().mask.sum(), SourceSet(q.getSources())))
    p.registerProperty('n', Datum.ROI, "give the number of pixels in an ROI",
                       lambda q: Datum(Datum.NUMBER, q.pixels(), SourceSet(q.getSources())))


