"""
Builtin functions and properties. Needs to be explicitly imported so the decorators run!
"""

from typing import List, SupportsFloat, Optional

import numpy as np

import pcot
from pcot import rois
from pcot.config import parserhook
from pcot.datum import Datum
from pcot.expressions import Parameter
from pcot.imagecube import ImageCube
from pcot.sources import SourceSet, MultiBandSource
from pcot.utils import image
from pcot.expressions.ops import combineImageWithNumberSources
from pcot.value import Value, add_sub_unc_list
from pcot.xform import XFormException
import cv2 as cv


# TODOUNCERTAINTY TEST
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
            dat = np.full((h, w), x.val.n, dtype=np.float32)
            if x.val.u > 0.0:
                unc = np.full((h, w), x.val.u, dtype=np.float32)
            else:
                unc = None
            imglist.append(ImageCube(dat, None, None, uncertainty=unc))
        else:
            raise XFormException('EXPR', 'arguments to merge must be images or numbers')

    # and merge
    bands = []
    banduncs = []
    banddqs = []

    sources = []
    for x in imglist:
        if x.channels == 1:
            bands.append(x.img[:h, :w])
            banduncs.append(x.uncertainty[:h, :w])
            banddqs.append(x.dq[:h, :w])
        else:
            bands = bands + image.imgsplit(x.img)
            banduncs = banduncs + image.imgsplit(x.uncertainty)
            banddqs = banddqs + image.imgsplit(x.dq)
        sources = sources + x.sources.sourceSets

    img = image.imgmerge(bands)
    unc = image.imgmerge(banduncs)
    dqs = image.imgmerge(banddqs)
    img = ImageCube(img, None, MultiBandSource(sources), uncertainty=unc, dq=dqs)

    return Datum(Datum.IMG, img)


# TODOUNCERTAINTY TEST
def funcGrey(args, optargs):
    """Greyscale conversion. If the optional second argument is nonzero, and the image has 3 channels, we'll use CV's
    conversion equation rather than just the mean. However, this loses uncertainty information. Otherwise uncertainty
    is calculated by adding together the channels in quadrature and then dividing the number of channels."""

    img = args[0].get(Datum.IMG)

    ss = SourceSet([img.sources, optargs[0].getSources()])
    sources = MultiBandSource([ss])

    if optargs[0].get(Datum.NUMBER).n != 0:
        if img.channels != 3:
            raise XFormException('DATA', "Image must be RGB for OpenCV greyscale conversion")
        img = ImageCube(cv.cvtColor(img.img, cv.COLOR_RGB2GRAY), img.mapping, sources)
    elif img.channels == 1:
        img = img.copy()  # 1 channel in the input, just copy it
    else:
        # create a transformation matrix specifying that the output is a single channel which
        # is the mean of all the channels in the source. Any uncertainy data will also be combined.
        mat = np.array([1 / img.channels] * img.channels).reshape((1, img.channels))
        out = cv.transform(img.img, mat)
        # uncertainty is messier - add the squared uncertainties, divide by N, and root.
        # DQs are dealt with by ORing all the bits together from each channel
        outu = np.zeros(img.uncertainty.shape[:2], dtype=np.float32)
        dq = np.zeros(img.dq.shape[:2], dtype=np.uint16)
        for i in range(0, img.channels):
            c = img.uncertainty[:, :, i]
            outu += c * c
            dq |= img.dq[:, :, i]
        # divide by the count and root
        outu = np.sqrt(outu / img.channels)
        img = ImageCube(out, img.mapping, sources, uncertainty=outu, dq=dq)
    return Datum(Datum.IMG, img)


# TODOUNCERTAINTY TEST
def funcCrop(args, _):
    img = args[0].get(Datum.IMG)
    x, y, w, h = [int(x.get(Datum.NUMBER).n) for x in args[1:]]
    out = img.img[y:y + h, x:x + w]
    dq = img.dq[y:y + h, x:x + w]
    unc = img.uncertainty[y:y + h, x:x + w]
    img = ImageCube(out, img.mapping, img.sources, dq=dq, uncertainty=unc)
    return Datum(Datum.IMG, img)


def funcROI(args: List[Datum], _):
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


def funcRGBImage(args, _):
    img = args[0].get(Datum.IMG)
    if img is not None:
        img = img.rgbImage()

    return Datum(Datum.IMG, img)


def funcTestImg(args, _):
    ct = args[0].get(Datum.NUMBER).n
    imgs = []
    uncs = []
    for i in range(0, int(ct)):
        imgs.append(np.full((20, 20), i, dtype=np.float32))
        uncs.append(np.full((20, 20), i * 0.1, dtype=np.float32))
    imgs = np.dstack(imgs)
    uncs = np.dstack(uncs)
    img = ImageCube(imgs, uncertainty=uncs)
    return Datum(Datum.IMG, img)


def funcV(args, optargs):
    # create a new nominal,uncertainty value - image or number - from the nominal values of two inputs.
    # So if you pass:
    #  image, image - one image with uncertainty taken from the nominal values of second image
    #  image, number - image with constant uncertainty
    #  number, image - constant grey image with uncertainty taken from the nominal values of second image (a bit weird)
    #  number, number - most common case, a number with uncertainty
    #
    # Any optional DQ is ORed into the DQ of the result - only works on numbers, though!

    t0 = args[0].tp
    t1 = args[1].tp
    v0 = args[0].get(t0)
    v1 = args[1].get(t1)
    s0 = args[0].sources
    s1 = args[1].sources

    dq = optargs[0].get(Datum.NUMBER)
    if dq is None:
        dq = dq.NONE
    else:
        dq = np.uint16(dq.n)

    if t0 == Datum.NUMBER:
        if t1 == Datum.NUMBER:
            # number, number
            return Datum(Datum.NUMBER, Value(v0.n, v1.n, dq), SourceSet([s0, s1]))
        else:
            # here, we're creating a number,uncimage pair
            i = np.full(v1.img.shape, v0.n, dtype=np.float32)
            s = combineImageWithNumberSources(v1, s0)
            img = ImageCube(i, uncertainty=v1.img, dq=v1.dq | dq, sources=s)
            return Datum(Datum.IMG, img)
    else:
        if t1 == Datum.NUMBER:
            # image, number
            i = np.full(v0.img.shape, v1.n, dtype=np.float32)
            s = combineImageWithNumberSources(v0, s1)
            img = ImageCube(v0.img, uncertainty=i, dq=v0.dq | dq, sources=s)
            return Datum(Datum.IMG, img)
        else:
            img = ImageCube(v0.img, uncertainty=v1.img, dq=v0.dq | v1.dq | dq,
                            sources=MultiBandSource.createBandwiseUnion([s0, s1]))
            return Datum(Datum.IMG, img)


def funcNominal(args: List[Datum], _):
    if args[0].tp == Datum.IMG:
        img = args[0].get(Datum.IMG)
        if img is not None:
            img = ImageCube(img.img, None, img.sources, rois=img.rois)
        return Datum(Datum.IMG, img)
    else:  # type is constrained to either image or number, so it's fine to do this
        n = args[0].get(Datum.NUMBER)
        return Datum(Datum.NUMBER, Value(n.n, 0), sources=args[0].sources)


def funcUncertainty(args: List[Datum], _):
    if args[0].tp == Datum.IMG:
        img = args[0].get(Datum.IMG)
        if img is not None:
            img = ImageCube(img.uncertainty, None, img.sources, rois=img.rois)
        return Datum(Datum.IMG, img)
    else:  # type is constrained to either image or number, so it's fine to do this
        n = args[0].get(Datum.NUMBER)
        return Datum(Datum.NUMBER, Value(n.u, 0), sources=args[0].sources)


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
            # 'img' is SourcesObtainable. Note that we set zero uncertainty here! TODO UNCERTAINTY!
            val = Value(float(newdata), 0.0)
            return Datum(Datum.NUMBER, val, img)
        else:
            raise XFormException('EXPR', 'internal: fn returns bad type in funcWrapper')
    elif d.tp == Datum.NUMBER:  # deal with numeric argument (always returns a numeric result)
        # get sources for all arguments
        ss = [a.getSources() for a in args]
        ss.append(d.getSources())
        val = Value(fn(d.val.n, *args), 0.0)  # TODO UNCERTAINTY!
        return Datum(Datum.NUMBER, val, SourceSet(ss))


def funcMarkSat(args: List[Datum], _):
    img = args[0].get(Datum.IMG)
    mn = args[1].get(Datum.NUMBER).n
    mx = args[2].get(Datum.NUMBER).n
    if img is None:
        return None

    subimage = img.subimage()
    data = subimage.masked(maskBadPixels=True)
    dq = np.where(data <= mn, pcot.dq.ERROR, 0).astype(np.uint16)
    dq |= np.where(data >= mx, pcot.dq.SAT, 0).astype(np.uint16)

    img = img.modifyWithSub(subimage, None, dqOR=dq, uncertainty=subimage.uncertainty)
    return Datum(Datum.IMG, img)


def statsWrapper(fn, fnu, d: List[Optional[Datum]], *args):
    """similar to funcWrapper, but can take lots of image and number arguments which it aggregates to do stats on.
    The result of fn must be a number. Works by flattening any images and concatenating them with any numbers,
    and doing the operation on the resulting data.

    fn generates the nominal value and takes the nominal values,
    fnu generates the uncertainty and takes nominal values and uncertainty."""

    intermediate = None
    uncintermediate = None

    sources = []
    for x in d:
        # get each datum, which is either numeric or an image.
        if x is None:
            continue
        elif x.isImage():
            # if an image, convert to a 1D array
            subimage = x.val.subimage()
            # we ignore "bad" pixels in the data
            mask = subimage.fullmask(maskBadPixels=True)
            cp = subimage.img.copy()
            cpu = subimage.uncertainty.copy()

            sources.append(x.sources)
            masked = np.ma.masked_array(cp, mask=~mask)
            uncmasked = np.ma.masked_array(cpu, mask=~mask)

            # we convert the data into a flat numpy array if it isn't one already
            if isinstance(masked, np.ma.masked_array):
                newdata = masked.compressed()  # convert to 1d and remove masked elements
            elif isinstance(masked, np.ndarray):
                newdata = masked.flatten()  # convert to 1d
            else:
                raise XFormException('EXPR', 'internal: data in masked array is wrong type in statsWrapper')
            if isinstance(uncmasked, np.ma.masked_array):
                uncnewdata = uncmasked.compressed()  # convert to 1d and remove masked elements
            elif isinstance(uncmasked, np.ndarray):
                uncnewdata = uncmasked.flatten()  # convert to 1d
            else:
                raise XFormException('EXPR', 'internal: data in uncmasked array is wrong type in statsWrapper')

        elif x.tp == Datum.NUMBER:
            # if a number, convert to a single-value array
            newdata = np.array([x.val.n], np.float32)
            uncnewdata = np.array([x.val.u], np.float32)
            sources.append(x.sources)
        else:
            raise XFormException('EXPR', 'internal: bad type passed to statsWrapper')

        # and concat it to the intermediate array
        if intermediate is None:
            intermediate = newdata
            uncintermediate = uncnewdata
        else:
            intermediate = np.concatenate((intermediate, newdata))
            uncintermediate = np.concatenate((uncintermediate, uncnewdata))

    # then we perform the function on the collated array
    # TODO UNCERTAINTY! It's ignored by this func TODOUNCERTAINTY
    val = fn(intermediate, *args)
    u = fnu(intermediate, uncintermediate, *args)
    return Datum(Datum.NUMBER, Value(val, u), SourceSet(sources))


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
    p.registerFunc("sqrt", "calculate the square root (note - uncertainty is cleared. Use ^0.5 instead).",
                   [Parameter("angle", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: funcWrapper(np.sqrt, args[0]))

    p.registerFunc("min",
                   "find the minimum value of the nominal values in a set of images and/or values. "
                   "Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.min, lambda n, u: 0, args), varargs=True)
    p.registerFunc("max",
                   "find the minimum value of the nominal values in a set of images and/or values. "
                   "Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.max, lambda n, u: 0, args), varargs=True)
    p.registerFunc("sd",
                   "find the standard deviation of the nominal values in a set of images and/or values. "
                   "Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.std, lambda n, u: 0, args), varargs=True)
    p.registerFunc("sum",
                   "find the sum of the nominal in a set of images and/or values. "
                   "Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect. "
                   "The SD of the result is the SD of the sum, not the individual values.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.sum, lambda n, u: add_sub_unc_list(u), args), varargs=True)
    p.registerFunc("mean",
                   "find the mean±sd of the nominal values of a set of images and/or values. "
                   "Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(np.mean, lambda n, u: np.std(n), args), varargs=True)

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
        "If input is an image, create an image made up of uncertainty data for all channels; if input is numeric,"
        " output the uncertainty. Ignores ROIs.",
        [Parameter("image", "the image to process", (Datum.IMG, Datum.NUMBER))],
        [],
        funcUncertainty
    )

    p.registerFunc(
        "nominal",
        "If input is an image, create an image made up of nominal data for all channels; if input is numeric,"
        " output the uncertainty. In other words, just remove the uncertainty. Ignores ROIs.",
        [Parameter("image", "the image to process", (Datum.IMG, Datum.NUMBER))],
        [],
        funcNominal
    )

    p.registerFunc(
        "rgb",
        "create a 3-channel image consisting of the current RGB mapping of the input image",
        [Parameter("image", "the image to process", Datum.IMG)],
        [],
        funcRGBImage
    )

    p.registerFunc(
        "v",
        "create a new value with uncertainty by combining two nominal values. These can be either numbers or images. "
        "Ignores and discards ROIs.",
        [
            Parameter("value", "the nominal value", (Datum.NUMBER, Datum.IMG)),
            Parameter("uncertainty", "the uncertainty", (Datum.NUMBER, Datum.IMG))
        ], [
            Parameter("dq",
                      "if present, a DQ bit field (e.g. 36 for COMPLEX|SAT) (only works on numeric args)",
                      Datum.NUMBER, deflt=0),
        ],
        funcV
    )

    p.registerFunc(
        "testimg",
        "create a test image consisting of N channels of data (1,2,3,..,n) and uncertainty (0.1,0.2,0.3,..,n)",
        [
            Parameter("count", "number of channels", Datum.NUMBER)
        ], [], funcTestImg
    )

    p.registerFunc(
        "marksat",
        "mark pixels outside a certain range as SAT or ERROR (i.e BAD)",
        [
            Parameter("image", "the input image", Datum.IMG),
            Parameter("min", "the minimum value below which pixels are ERROR", Datum.NUMBER),
            Parameter("max", "the maximum value above which pixels are SAT", Datum.NUMBER)
        ], [], funcMarkSat
    )


@parserhook
def registerBuiltinProperties(p):
    p.registerProperty('w', Datum.IMG,
                       "give the width of an image in pixels (if there are ROIs, give the width of the BB of the ROI union)",
                       lambda q: Datum(Datum.NUMBER, Value(q.subimage().bb.w, 0.0), SourceSet(q.getSources())))
    p.registerProperty('w', Datum.ROI, "give the width of an ROI in pixels",
                       lambda q: Datum(Datum.NUMBER, Value(q.bb().w, 0.0), SourceSet(q.getSources())))
    p.registerProperty('h', Datum.IMG,
                       "give the height of an image in pixels (if there are ROIs, give the width of the BB of the ROI union)",
                       lambda q: Datum(Datum.NUMBER, Value(q.subimage().bb.h, 0.0), SourceSet(q.getSources())))
    p.registerProperty('h', Datum.ROI, "give the width of an ROI in pixels",
                       lambda q: Datum(Datum.NUMBER, Value(q.bb().h, 0.0), SourceSet(q.getSources())))

    p.registerProperty('n', Datum.IMG,
                       "give the area of an image in pixels (if there are ROIs, give the number of pixels in the ROI union)",
                       lambda q: Datum(Datum.NUMBER, Value(q.subimage().mask.sum(), 0.0), SourceSet(q.getSources())))
    p.registerProperty('n', Datum.ROI, "give the number of pixels in an ROI",
                       lambda q: Datum(Datum.NUMBER, Value(q.pixels(), 0.0), SourceSet(q.getSources())))
