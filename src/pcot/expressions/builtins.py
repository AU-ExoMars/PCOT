"""
Builtin functions and properties. Needs to be explicitly imported so the decorators run!
"""
from typing import List, Optional, Callable

import numpy as np

from pcot import dq
from pcot.config import parserhook
from pcot.datum import Datum
from pcot.expressions import Parameter
from pcot.expressions.datumfuncs import datumfunc
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
