"""
Builtin functions and properties. Needs to be explicitly imported so the decorators run!
"""
from typing import List, Optional, Callable

import numpy as np

import pcot
import pcot.dq
from pcot import dq
from pcot.config import parserhook
from pcot.datum import Datum
from pcot.expressions import Parameter
from pcot.expressions.datumfuncs import datumfunc
from pcot.filters import Filter
from pcot.imagecube import ImageCube
from pcot.sources import SourceSet, MultiBandSource, Source, StringExternal
from pcot.utils.deb import Timer
from pcot.utils.flood import FloodFillParams, FastFloodFiller
from pcot.value import Value, add_sub_unc_list
from pcot.xform import XFormException


def funcWrapper(fn: Callable[[Value], Value], d: Datum) -> Datum:
    """Takes a function which takes and returns Value, and a datum. This is a utility for dealing with
    functions. For images, it strips out the relevant pixels (subject to ROIs) and creates a masked array. However, BAD
    pixels are included. It then performs the operation and creates a new image which is a copy of the
    input with the new data spliced in."""

    if d is None:
        return None
    elif d.tp == Datum.NUMBER:  # deal with numeric argument (always returns a numeric result)
        # get sources for all arguments
        ss = d.getSources()
        rv = fn(d.val)
        return Datum(Datum.NUMBER, rv, SourceSet(ss))
    elif d.isImage():
        img = d.val
        ss = d.sources
        subimage = img.subimage()

        # make copies of the source data into which we will splice the results
        imgcopy = subimage.img.copy()
        unccopy = subimage.uncertainty.copy()
        dqcopy = subimage.dq.copy()

        # Perform the calculation on the entire subimage rectangle, but only the results covered by ROI
        # will be spliced back into the image (modifyWithSub does this).
        v = Value(imgcopy, unccopy, dqcopy)

        rv = fn(v)
        # depending on the result type..
        if rv.isscalar():
            # ...either use it as a number datum
            return Datum(Datum.NUMBER, rv, ss)
        else:
            # ...or splice it back into the image
            img = img.modifyWithSub(subimage, rv.n, uncertainty=rv.u, dqv=rv.dq)
            return Datum(Datum.IMG, img)





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


def funcSetCWL(args: List[Datum], _):
    img = args[0].get(Datum.IMG)
    cwl = args[1].get(Datum.NUMBER).n

    if img is None:
        return None

    if img.channels != 1:
        raise XFormException('EXPR', 'setcwl must take a single channel image')
    img = img.copy()
    img.sources = MultiBandSource([Source().setBand(Filter(float(cwl), 30, 1.0, idx=0))])
    return Datum(Datum.IMG, img)


def statsWrapper(fn, d: List[Optional[Datum]], *args) -> Datum:
    """similar to funcWrapper, but can take lots of image and number arguments which it aggregates to do stats on.
    The result of fn must be a number. Works by flattening any images and concatenating them with any numbers,
    and doing the operation on the resulting data.

    fn takes a tuple of nominal and uncertainty values compressed into a 1D array, and returns a Value.
    """

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

    # then we perform the function on the collated arrays
    val = fn(intermediate, uncintermediate, *args)
    return Datum(Datum.NUMBER, val, SourceSet(sources))


def funcRotate(args: List[Datum], _):
    img: ImageCube = args[0].get(Datum.IMG)
    if img is None:
        return None
    angle = args[1].get(Datum.NUMBER).n
    # only permit multiples of 90 degrees, giving an error otherwise
    if angle % 90 != 0:
        raise XFormException('DATA', 'rotation angle must be a multiple of 90 degrees')

    img = img.rotate(angle)
    return Datum(Datum.IMG, img)


def funcFlipV(args: List[Datum], _):
    img: ImageCube = args[0].get(Datum.IMG)
    if img is None:
        return None
    img = img.flip(vertical=True)
    return Datum(Datum.IMG, img)


def funcFlipH(args: List[Datum], _):
    img: ImageCube = args[0].get(Datum.IMG)
    if img is None:
        return None
    img = img.flip(vertical=False)
    return Datum(Datum.IMG, img)


def funcStripROI(args: List[Datum], _):
    img: ImageCube = args[0].get(Datum.IMG)
    if img is None:
        return None
    img = img.shallowCopy()
    img.rois = []
    return Datum(Datum.IMG, img)


def funcFloodTest(args: List[Datum], _):
    # we'll operate on the entire image
    img: ImageCube = args[0].get(Datum.IMG)
    if img is None:
        return None
    x = int(args[1].get(Datum.NUMBER).n)
    y = int(args[2].get(Datum.NUMBER).n)
    thresh = args[3].get(Datum.NUMBER).n

    f = FastFloodFiller(img, FloodFillParams(10, img.w * img.h, thresh))
    with Timer("flood", show=Timer.UILOG):
        roi = f.fillToPaintedRegion(x, y)

    # we need to copy the image to add the ROI
    img = img.shallowCopy()
    if roi is not None:
        img.rois.append(roi)
    else:
        raise XFormException('DATA', 'flood fill failed (too few or too many pixels)')

    return Datum(Datum.IMG, img)


def funcAssignSources(args: List[Datum], _):
    img1: ImageCube = args[0].get(Datum.IMG)
    img2: ImageCube = args[1].get(Datum.IMG)
    if img1 is None or img2 is None:
        return None
    # make sure they have the same number of channels
    if img1.channels != img2.channels:
        raise XFormException('DATA', 'images in assignsources must have the same number of channels')
    # run through the image sources and make sure each image has only one source, and unify them
    sources = []
    for i in range(img1.channels):
        f1 = img1.filter(i)
        f2 = img2.filter(i)
        if f1 is None:
            raise XFormException('DATA', 'image 1 in assignsources must have a single source for each channel')
        if f2 is None:
            raise XFormException('DATA', 'image 2 in assignfilters must have a single source for each channel')
        if f1.cwl != f2.cwl or f1.fwhm != f2.fwhm:
            raise XFormException('DATA', 'filters in assignfilters must have the same cwl and fwhm')
        sources.append(Source().setBand(f1).setExternal(StringExternal("assignsources", f"unified-{f1.name}")))

    # now we can create the new image - it's image2 with the sources replaced with those of image1
    out = img2.copy()
    out.sources = MultiBandSource(sources)
    return Datum(Datum.IMG, out)


@parserhook
def registerBuiltinFunctions(p):
    p.registerFunc("min",
                   "find the minimum value of the nominal values in a set of images and/or values. "
                   "Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(lambda n, u: Value(np.min(n), 0.0, dq.NOUNCERTAINTY), args),
                   varargs=True)
    p.registerFunc("max",
                   "find the minimum value of the nominal values in a set of images and/or values. "
                   "Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(lambda n, u: Value(np.max(n), 0.0, dq.NOUNCERTAINTY), args),
                   varargs=True)
    p.registerFunc("sum",
                   "find the sum of the nominal in a set of images and/or values. "
                   "Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect. "
                   "The SD of the result is the SD of the sum, not the individual values.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(lambda n, u: Value(np.sum(n), add_sub_unc_list(u), dq.NONE),
                                                      args), varargs=True)

    def pooled_sd(n, u):
        """Returns pooled standard deviation for an array of nominal values and an array of stddevs."""
        # "Thus the variance of the pooled set is the mean of the variances plus the variance of the means."
        # by https://arxiv.org/ftp/arxiv/papers/1007/1007.1012.pdf
        # the variance of the means is n.var()
        # the mean of the variances is np.mean(u**2) (since u is stddev, and stddev**2 is variance)
        # so the sum of those is pooled variance. Root that to get the pooled stddev.
        # There is a similar calculation in xformspectrum!
        return np.sqrt(n.var() + np.mean(u ** 2))

    p.registerFunc("mean",
                   "find the mean±sd of the values of a set of images and/or scalars. "
                   "Uncertainties in the data will be pooled. Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(lambda n, u: Value(np.mean(n), pooled_sd(n, u), dq.NONE),
                                                      args), varargs=True)
    p.registerFunc("sd",
                   "find the standard deviation of the nominal values in a set of images and/or scalars. "
                   "Uncertainties in the data will be pooled. Images will be flattened into a list of values, "
                   "so the result for multiband images may not be what you expect.",
                   [Parameter("val", "value(s) to input", (Datum.NUMBER, Datum.IMG))],
                   [],
                   lambda args, optargs: statsWrapper(lambda n, u: Value(pooled_sd(n, u), 0, dq.NOUNCERTAINTY),
                                                      args), varargs=True)

    p.registerFunc(
        "marksat",
        "mark pixels outside a certain range as SAT or ERROR (i.e BAD)",
        [
            Parameter("image", "the input image", Datum.IMG),
            Parameter("min", "the minimum value below which pixels are ERROR", Datum.NUMBER),
            Parameter("max", "the maximum value above which pixels are SAT", Datum.NUMBER)
        ], [], funcMarkSat
    )

    p.registerFunc(
        "setcwl",
        "Given an 1-band image, 'fake' a filter of a given CWL and assign it. The image itself is unchanged. This is "
        "used in testing only.",
        [
            Parameter("image", "the input image", Datum.IMG),
            Parameter("cwl", "the fake filter CWL", Datum.NUMBER),
        ], [], funcSetCWL
    ),

    p.registerFunc(
        "assignsources",
        "Given a pair of images with different sources which nevertheless have the same filters (cwl and fwhm) on"
        "corresponding bands, create a new image with data from the second but sources from the first."
        "Should probably be used in testing only.",
        [
            Parameter("src", "source of filter data", Datum.IMG),
            Parameter("dest", "image to receive filter data", Datum.IMG),
        ], [], funcAssignSources
    )

    p.registerFunc(
        "rotate", "rotate an image by a multiple of 90 degrees clockwise",
        [
            Parameter("image", "the image to rotate", Datum.IMG),
            Parameter("angle", "the angle to rotate by (degrees)", Datum.NUMBER),
        ], [], funcRotate
    )

    p.registerFunc(
        "flipv", "flip an image vertically",
        [
            Parameter("image", "the image to flip", Datum.IMG),
        ], [], funcFlipV
    )

    p.registerFunc(
        "fliph", "flip an image horizontally",
        [
            Parameter("image", "the image to flip", Datum.IMG),
        ], [], funcFlipH
    )

    p.registerFunc(
        "striproi", "strip all ROIs from an image",
        [
            Parameter("image", "the image to strip ROIs from", Datum.IMG),
        ], [], funcStripROI
    )

    #    p.registerFunc(
    #        'testimg', 'Load test image',
    #        [
    #            Parameter('imageidx', 'image index', Datum.NUMBER)
    #        ], [], funcTestImg
    #    )

    p.registerFunc(
        'floodtest', 'Flood fill test',
        [
            Parameter('image', 'image to flood', Datum.IMG),
            Parameter('x', 'x coordinate of seed point', Datum.NUMBER),
            Parameter('y', 'y coordinate of seed point', Datum.NUMBER),
            Parameter('thresh', 'threshold', Datum.NUMBER),
        ], [], funcFloodTest
    )

    # register the built-in functions that have been registered through the datumfunc mechanism.
    for _, f in datumfunc.registry.items():
        p.registerFunc(f.name, f.description, f.mandatoryParams, f.optParams, f.exprfunc, varargs=f.varargs)


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
