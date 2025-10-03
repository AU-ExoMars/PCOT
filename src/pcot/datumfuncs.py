import builtins
from typing import Callable

import cv2 as cv
import numpy as np
import logging

import pcot.dq
from pcot import rois, operations, dq
from pcot.assets import getAssetPath
from pcot.datum import Datum
from pcot.dq import NODATA
from pcot.expressions.register import datumfunc
from pcot.expressions.ops import combineImageWithNumberSources
from pcot.cameras.filters import Filter
from pcot.imagecube import ImageCube
from pcot.rois import ROI, ROICircle
from pcot.sources import MultiBandSource, SourceSet, Source, StringExternal, nullSourceSet
from pcot.utils import image
from pcot.utils.deb import Timer
from pcot.utils.geom import Rect
from pcot.utils.maths import pooled_sd
from pcot.utils.table import Table
from pcot.value import Value
from pcot.xform import XFormException

logger = logging.getLogger(__name__)


@datumfunc
def flat(val, *args):
    """
    Turns a list of vectors, images and numbers into a single vector, by flattening each into a 1D vector
    and concatenating them all together. Data with any of the dq.BAD bits is removed.

    @param val:img,number:the first value (image, number or vector)
    """

    intermediate = None
    uncintermediate = None
    dqintermediate = None

    d = [val] + list(args)

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
            cpd = subimage.dq.copy()

            sources.append(x.sources)
            masked = np.ma.masked_array(cp, mask=~mask)
            uncmasked = np.ma.masked_array(cpu, mask=~mask)
            dqmasked = np.ma.masked_array(cpd, mask=~mask)

            # we convert the data into a flat numpy array if it isn't one already
            if isinstance(masked, np.ma.masked_array):
                newdata = masked.compressed()  # convert to 1d and remove masked elements
            elif isinstance(masked, np.ndarray):
                newdata = masked.flatten()  # convert to 1d
            else:
                raise XFormException('EXPR', 'internal: data in masked array is wrong type in flat()')

            if isinstance(uncmasked, np.ma.masked_array):
                uncnewdata = uncmasked.compressed()  # convert to 1d and remove masked elements
            elif isinstance(uncmasked, np.ndarray):
                uncnewdata = uncmasked.flatten()  # convert to 1d
            else:
                raise XFormException('EXPR', 'internal: data in uncmasked array is wrong type in flat()')

            if isinstance(dqmasked, np.ma.masked_array):
                dqnewdata = dqmasked.compressed()
            elif isinstance(dqmasked, np.ndarray):
                dqnewdata = dqmasked.flatten()
            else:
                raise XFormException('EXPR', 'internal: data in dqmasked array is wrong type in flat()')

        elif x.tp == Datum.NUMBER:
            if x.val.isscalar():
                # if a number, convert to a single-value array
                if not x.val.dq & dq.BAD:
                    newdata = np.array([x.val.n], np.float32)
                    uncnewdata = np.array([x.val.u], np.float32)
                    dqnewdata = np.array([x.val.dq], np.uint16)
                else:
                    continue  # skip bad data
            else:
                # vector data. We need to remove any bad data with indexing tricks
                good_indices = (x.val.dq & dq.BAD) == 0
                newdata = x.val.n[good_indices]
                uncnewdata = x.val.u[good_indices]
                dqnewdata = x.val.dq[good_indices]
                if len(newdata) == 0:
                    continue  # if all data bad, skip it
            sources.append(x.sources)
        else:
            raise XFormException('EXPR', 'internal: bad type passed to flat()')

        # and concat it to the intermediate array
        if intermediate is None:
            intermediate = newdata
            uncintermediate = uncnewdata
            dqintermediate = dqnewdata
        else:
            intermediate = np.concatenate((intermediate, newdata))
            uncintermediate = np.concatenate((uncintermediate, uncnewdata))
            dqintermediate = np.concatenate((dqintermediate, dqnewdata))

    # then create the value
    val = Value(intermediate, uncintermediate, dqintermediate)
    return Datum(Datum.NUMBER, val, SourceSet(sources))


def func_wrapper(fn: Callable[[Value], Value], d: Datum) -> Datum:
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
    else:
        raise XFormException('EXPR', 'unsupported type for function')


def stats_wrapper(val, func):
    """Takes a function that operates on a tuple of val,unc,dq and returns same
    """
    if val.tp == Datum.NUMBER:
        ns = val.get(Datum.NUMBER).n
        us = val.get(Datum.NUMBER).u
        dqs = val.get(Datum.NUMBER).dq
        nr, ur, dqr = func(ns, us, dqs)
        return Datum(Datum.NUMBER, Value(nr, ur, dqr), sources=val.sources)
    elif val.isImage():
        img = val.get(Datum.IMG)
        if img is None:
            return None

        # get the subimage (i.e. only the part covered by ROIs if there are any)
        # and mask out the bad pixels
        subimage = img.subimage()
        # I was making a copy, but I don't think it's needed.
        imgn_masked, imgu_masked, imgd_masked = subimage.masked_all(True)

        if img.channels == 1:
            # mono image
            ns, us, ds = func(imgn_masked, imgu_masked, imgd_masked)
        else:
            # split the image into bands
            ns = image.imgsplit(imgn_masked)
            us = image.imgsplit(imgu_masked)
            ds = image.imgsplit(imgd_masked)
            v = [func(ns[i], us[i], ds[i]) for i in range(0, len(ns))]
            # we now have a list of tuples. We want to get from this:
            # [(n,u,d),(n,u,d),(n,u,d) .. ] to [(n,n,n,n),(u,u,u,u),(d,d,d,d)]
            # so we use zip to transpose the list of tuples
            ns, us, ds = list(zip(*v))
        return Datum(Datum.NUMBER, Value(ns, us, ds), img.sources)
    else:
        # shouldn't happen because we check types
        raise XFormException('DATA', 'stats functions can only take numbers or images')


@datumfunc  # NOUNCERTAINTYTEST
def merge(img1, *remainingargs):
    """merge a number of images into multiple bands of a single image. If the image has multiple bands
    they will all become bands in the new image.
    @param img1:   img : first image
    """

    args = [img1] + list(remainingargs)
    if any([x is None for x in args]):
        raise XFormException('EXPR', 'argument is None for merge')

    if not any([x.isImage() for x in args]):
        raise XFormException('EXPR', 'merge must take at least one image')

    # check sizes of all images are the same
    imgargs = [x.get(Datum.IMG) for x in args if x.isImage()]

    if any([x is None for x in imgargs]):
        raise XFormException('EXPR', 'argument is not an image for merge')

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
@datumfunc  # NOUNCERTAINTYTEST
def grey(img, opencv=0):
    """
    Greyscale conversion. If the optional second argument is nonzero, and the image has 3 channels, we'll use CV's
    conversion equation rather than just the mean. **However, this loses uncertainty information.**
    Otherwise uncertainty
    is calculated by adding together the channels in quadrature and then dividing the number of channels.

    @param img:img:image to convert
    @param opencv:number:if nonzero, use opencv greyscale conversion (default is 0)
    """

    ss = SourceSet(img.sources)
    # opencv is not actually an int due to what the wrappers do. It's a Datum
    # containing a number. Don't worry about the warning here.
    sources = MultiBandSource([ss.add(opencv.getSources())])

    img = img.get(Datum.IMG)
    if img.channels == 1:
        img = img.copy()  # 1 channel in the input, just copy it
    else:
        # DQs are dealt with by ORing all the bits together from each channel
        dq = np.zeros(img.dq.shape[:2], dtype=np.uint16)
        for i in range(0, img.channels):
            dq |= img.dq[:, :, i]

        if opencv.get(Datum.NUMBER).n != 0:  # if the opt arg is nonzero, use opencv - but no unc!
            if img.channels != 3:
                raise XFormException('DATA', "Image must be RGB for OpenCV greyscale conversion")
            img = ImageCube(cv.cvtColor(img.img, cv.COLOR_RGB2GRAY), img.mapping, sources, dq=dq, rois=img.rois)
        else:
            # 'out' will be the greyscale image found by calculating the mean of all channels in img.img
            out = np.mean(img.img, axis=2).astype(np.float32)

            # to calculate the uncertainty, the pooled variance will be the variance of the means, plus the
            # mean of the variances. So first we'll find the variances of each channel (this is the "variance
            # of the means"). We can't know the number of samples that went into each pixel, so we'll assume
            # they're all the same.
            # See Rudmin, J. W. (2010). Calculating the exact pooled variance. arXiv preprint arXiv:1007.1012
            varchans = np.var(img.img, axis=2)
            # then we calculate the mean of the variances - to do this, we need to square the uncertainty (to give
            # us variance) and calculate the mean per pixel.
            outu = np.mean(np.square(img.uncertainty), axis=2)
            # we can then add these together - that gives the pooled variance, which we can root to get the pooled
            # standard deviation.
            outu = np.sqrt(outu + varchans)

            img = ImageCube(out, img.mapping, sources, uncertainty=outu, dq=dq, rois=img.rois)
    return Datum(Datum.IMG, img)


@datumfunc  # NOUNCERTAINTYTEST
def crop(img, x, y, w, h):
    """
    Crop an image to a rectangle
    @param img:img:the image to crop
    @param x:number:x coordinate of top left corner
    @param y:number:y coordinate of top left corner
    @param w:number:width of rectangle
    @param h:number:height of rectangle
    """
    # add the sources of the numbers (pretty much always null) to the
    # sources of the cropped image
    numericSources = SourceSet([a.getSources() for a in [x, y, w, h]])
    img = img.get(Datum.IMG)
    sources = img.sources.copy().addSetToAllBands(numericSources)

    x = int(x.get(Datum.NUMBER).n)
    y = int(y.get(Datum.NUMBER).n)
    w = int(w.get(Datum.NUMBER).n)
    h = int(h.get(Datum.NUMBER).n)

    if x < 0 or y < 0:
        raise XFormException('DATA', 'crop rectangle must have non-negative origin')

    if w <= 0 or h <= 0:
        raise XFormException('DATA', 'crop rectangle must have positive width and height')

    out = img.img[y:y + h, x:x + w]
    dq = img.dq[y:y + h, x:x + w]
    unc = img.uncertainty[y:y + h, x:x + w]
    img = ImageCube(out, img.mapping, sources, dq=dq, uncertainty=unc)
    return Datum(Datum.IMG, img)


@datumfunc
def roi(img):
    """Extract a single combined ROI from all ROIs on the image. If no ROIs are present,
    will return a single rectangular ROI covering the entire image.
    @param img:img:the image to extract the ROI from
    """
    img = img.get(Datum.IMG)
    if len(img.rois) == 0:
        # No ROIs at all? Make one out of the image.
        r = rois.ROIRect()
        r.set(0, 0, img.w, img.h)
    elif len(img.rois) == 1:
        # One ROI only? Use that (not a copy).
        r = img.rois[0]
    else:
        # Some ROIs? Make a new union ROI out of them all
        r = rois.ROI.roiUnion(img.rois)
    return Datum(Datum.ROI, r, sources=r.getSources())


@datumfunc
def addroi(img, r):
    """
    Add an ROI to an image's ROIs
    @param img:img:the image to add the ROI to
    @param r:roi:the ROI to add
    """
    img = img.get(Datum.IMG)
    if img is not None:
        r = r.get(Datum.ROI)
        if r is not None:
            img = img.copy()
            img.rois.append(r)
        return Datum(Datum.IMG, img)
    else:
        return Datum.null


@datumfunc
def rgb(img):
    """
    create a 3-channel image consisting of the current RGB mapping of the input image.
    NOTE: changing the mapping on a node does NOT cause the downstream nodes to run - you
    will have to click "Run All" to make an expr node with rgb() recalculate itself.
    @param img:img:the image to convert
    """
    img = img.get(Datum.IMG)
    if img is not None:
        return Datum(Datum.IMG, img.rgbImage())
    else:
        return Datum.null


@datumfunc
def v(n, u, dqbits=0):
    """
    create a new value with uncertainty by combining two values. These can be either numbers or images. "
    Ignores and discards ROIs.

    @param n:number,img:the nominal value
    @param u:number,img:the uncertainty
    @param dqbits:number: if present, the DQ bits to apply to the result
    """
    t0 = n.tp
    t1 = u.tp
    v0 = n.get(t0)
    v1 = u.get(t1)
    s0 = n.sources
    s1 = u.sources

    dq = dqbits.get(Datum.NUMBER)
    if dq is None:
        dq = pcot.dq.NONE
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
            # or in the new DQ but remove no uncertainty, unless it's in the data.
            dqimg = (v1.dq | dq) & ~pcot.dq.NOUNCERTAINTY

            img = ImageCube(i, uncertainty=v1.img, dq=dqimg, sources=s)
            return Datum(Datum.IMG, img)
    else:
        if t1 == Datum.NUMBER:
            # image, number
            i = np.full(v0.img.shape, v1.n, dtype=np.float32)
            s = combineImageWithNumberSources(v0, s1)
            dqimg = (v0.dq | dq) & ~pcot.dq.NOUNCERTAINTY
            img = ImageCube(v0.img, uncertainty=i, dq=dqimg, sources=s)
            return Datum(Datum.IMG, img)
        else:
            dqimg = (v0.dq | v1.dq | dq) & ~pcot.dq.NOUNCERTAINTY
            img = ImageCube(v0.img, uncertainty=v1.img, dq=dqimg,
                            sources=MultiBandSource.createBandwiseUnion([s0, s1]))
            return Datum(Datum.IMG, img)


@datumfunc
def nominal(d):
    """
    If input is an image, create an image made up of the nominal (mean) pixel values for all bands - i.e.
    an image with no uncertainty; if input is numeric,
    output the nominal value. Ignores ROIs.
    @param d:number,img:the value or image
    """
    if d.tp == Datum.IMG:
        img = d.get(Datum.IMG)
        if img is not None:
            img = ImageCube(img.img, None, img.sources, rois=img.rois)
        return Datum(Datum.IMG, img)
    else:  # type is constrained to either image or number, so it's fine to do this
        n = d.get(Datum.NUMBER)
        return Datum(Datum.NUMBER, Value(n.n, 0), sources=d.sources)


@datumfunc
def uncertainty(d):
    """
    If input is an image, create an image made up of uncertainty data for all bands; if input is numeric,
    output the uncertainty. Ignores ROIs.

    @param d:number,img:the value or image
    """
    if d.tp == Datum.IMG:
        img = d.get(Datum.IMG)
        if img is not None:
            img = ImageCube(img.uncertainty, None, img.sources, rois=img.rois)
        return Datum(Datum.IMG, img)
    else:  # type is constrained to either image or number, so it's fine to do this
        n = d.get(Datum.NUMBER)
        return Datum(Datum.NUMBER, Value(n.u, 0), sources=d.sources)


@datumfunc
def sin(a):
    """
    Calculate sine of an angle in radians
    @param a:img,number:the angle (or image in which each pixel is a single angle)
    """
    return func_wrapper(lambda xx: xx.sin(), a)


@datumfunc
def cos(a):
    """
    Calculate cosine of an angle in radians
    @param a:img,number:the angle (or image in which each pixel is a single angle)
    """
    return func_wrapper(lambda xx: xx.cos(), a)


@datumfunc
def tan(a):
    """
    Calculate tangent of an angle in radians
    @param a:img,number:the angle (or image in which each pixel is a single angle)
    """
    return func_wrapper(lambda xx: xx.tan(), a)


@datumfunc
def sqrt(a):
    """
    Calculate square root
    @param a:img,number:values (image or number)
    """
    return func_wrapper(lambda xx: xx.sqrt(), a)


@datumfunc
def abs(a):  # careful now, we're shadowing the builtin "abs" here.
    """
    Calculate absolute value
    @param a:img,number:values (image or number)
    """
    # We don't want to inadvertently recurse, so call the builtin
    # abs function.
    return func_wrapper(lambda xx: builtins.abs(xx), a)


@datumfunc
def vec(s1, *remainingargs):
    """
    Create a 1D numeric vector from several scalars or vectors.
    @param s1:number:the first scalar or vector
    """
    args = [s1] + list(remainingargs)
    if any([x is None for x in args]):
        raise XFormException('EXPR', 'argument is None for vec')

    if any([x.tp != Datum.NUMBER for x in args]):
        raise XFormException('EXPR', 'vec must take only numbers')

    # extract numeric values and concatenate them
    values = [x.get(Datum.NUMBER) for x in args]

    def concat(xx, dtype):
        """Take a list of mixed scalar and 1D numpy arrays. Concatenate into
        a single 1D numpy array."""
        es = [np.array([e], dtype=dtype) if np.isscalar(e) else e for e in xx]
        return np.concatenate(es)

    ns = concat([x.n for x in values], np.float32)
    us = concat([x.u for x in values], np.float32)
    dqs = concat([x.dq for x in values], np.uint16)

    # now build our value
    return Datum(Datum.NUMBER, Value(ns, us, dqs), sources=SourceSet([x.sources for x in args]))


testImageCache = {}


@datumfunc
def testimg(index, usetestfilters=0):
    """
    Load a test image.
    @param index : number : the index of the image to load
    @param usetestfilters : number : if nonzero, a set of test filter sources for the TEST camera will be created. Default 0.
    """
    fileList = ("marsRGB.png", "gradRGB.png", "corrib.png", "tstreg1.png", "tstreg2.png", "simpct.png")
    n = int(index.get(Datum.NUMBER).n)
    if n < 0:
        raise XFormException('DATA', 'negative test file index')
    n %= len(fileList)

    usetestfilters = int(usetestfilters.get(Datum.NUMBER).n)
    global testImageCache
    name_for_cache = f"{n}_{usetestfilters}"        # we keep different entries for usetestfilters and not.
    if name_for_cache in testImageCache:
        img = testImageCache[name_for_cache]
    else:
        try:
            p = getAssetPath(fileList[n])
        except FileNotFoundError as e:
            raise XFormException('DATA', f"cannot find test image{fileList[n]}")

        # create fake sources
        if usetestfilters != 0:
            # you'll need the "test" camera in your cameras to get the filters
            from pcot.cameras import getCamera
            ext = StringExternal(f"T{n}", f"Test Image {n}")
            cam = getCamera("TEST")
            rs = Source().setBand(cam.getFilter("RED")).setExternal(ext)
            gs = Source().setBand(cam.getFilter("GREEN")).setExternal(ext)
            bs = Source().setBand(cam.getFilter("BLUE")).setExternal(ext)
            sources = MultiBandSource([rs, gs, bs])
        else:
            sources = None

        img = ImageCube.load(p, None, sources)
        testImageCache[name_for_cache] = img

    return Datum(Datum.IMG, img)


@datumfunc
def marksat(img, mn=0, mx=1.0):
    """
    mark pixels outside a certain range as SAT or ERROR in the DQ bits.
    Pixels outside any ROI will be ignored, as will any pixels already
    marked as BAD.

    @param img:img:image to mark
    @param mn:number:minimum value - pixels below or equal to this will be marked as ERROR
    @param mx:number:maximum value - pixels above or equal to this will be marked as SAT
    """
    img = img.get(Datum.IMG)
    mn = mn.get(Datum.NUMBER).n
    mx = mx.get(Datum.NUMBER).n

    if img is None:
        return None

    subimage = img.subimage()
    data = subimage.masked()

    dq = np.where(data <= mn, pcot.dq.ZERO, 0).astype(np.uint16)
    dq |= np.where(data >= mx, pcot.dq.SAT, 0).astype(np.uint16)

    img = img.modifyWithSub(subimage, None,
                            dqOR=dq, uncertainty=subimage.uncertainty,
                            dontWriteBadPixels=True)
    return Datum(Datum.IMG, img)


@datumfunc
def setcwl(img, cwl):
    """
    Given a 1-band image, create a 'fake' filter with a given centre wavelength and assign it.
    The transmission of the filter is 1.0, and the fwhm is 30. The image itself is unchanged. This is used in testing only.
    @param img:img:image to set
    @param cwl:number:the fake filter CWL
    """

    img = img.get(Datum.IMG)
    cwl = cwl.get(Datum.NUMBER).n

    if img is None:
        return None

    if img.channels != 1:
        raise XFormException('EXPR', 'setcwl must take a single channel image')
    img = img.copy()
    img.sources = MultiBandSource([Source().setBand(Filter(float(cwl), 30, 1.0))])
    return Datum(Datum.IMG, img)


@datumfunc
def mean(val):
    """
    Find the mean±sd of a Datum. This does different things depending on what kind of Datum we are dealing with.
    For a scalar, it just returns the scalar. For a vector, it returns the mean and sd of the vector. For an
    image, it returns a vector of the means and sds of each channel.
    Pixels with "bad" DQ bits will be ignored.


    @param val:img,number:the value to process
    """
    return stats_wrapper(val,
                         lambda n, u, d: (np.mean(n), pooled_sd(n, u), pcot.dq.NONE))


@datumfunc
def sd(val):
    """Find the SD of a Datum. This does different things depending on what kind of Datum we are dealing with.
    For a scalar, it just returns 0. For a vector or single-channel image, it returns a scalar. For an image, it returns a
    vector of the SDs of each channel. Because each individual value in the input set can have its own uncertainty, the
    uncertainty is pooled - the pooled variance is the mean of the variances plus the variance of the means
    (Rudmin, J. W. (2010). Calculating the exact pooled variance. arXiv preprint arXiv:1007.1012). For pooling, we make
    the assumption that the number of items in each input subset (e.g. each pixel) is the same.
    Pixels with "bad" DQ bits will be ignored.

    @param val:img,number:the value to process
    """

    return stats_wrapper(val,
                         lambda n, u, d: (pooled_sd(n, u), 0, pcot.dq.NONE))


def minmax(f, n, u, d):
    """Find the minimum and maximum of a set of values, with uncertainty. This is a helper function for min and max;
    you pass np.argmin or np.argmax depending on what you want. The arrays passed in are the individual arrays which
    make up a value or image, and they can be of any dimensionality."""
    if np.isscalar(n):
        return n, u, d
    else:
        # find the index of the minimum value
        idx = np.unravel_index(f(n), n.shape)
        return n[idx], u[idx], d[idx]


@datumfunc
def min(val):
    """
    Find the minimum of a Datum. For a multiband image, returns a vector of the minimum value of each band.
    For a single band image, a scalar, or a vector, returns a scalar.
    Pixels with "bad" DQ bits will be ignored.

    See also the & (AND) operator, which will find the minimum of two values (or images, vectors etc).

    @param val:img,number:value to process
    """

    return stats_wrapper(val, lambda n, u, d: minmax(np.argmin, n, u, d))


@datumfunc
def max(val):
    """
    Find the maximum of a Datum. For a multiband image, returns a vector of the maximum of each band.
    For a single band image, a scalar, or a vector, returns a scalar.
    Pixels with "bad" DQ bits will be ignored.

    See also the | (OR) operator, which will find the minimum of two values (or images, vectors etc).

    @param val:img,number:value to process
    """
    return stats_wrapper(val, lambda n, u, d: minmax(np.argmax, n, u, d))


@datumfunc
def sum(val):
    """
    Find the sum of a Datum. For a multiband image, returns a vector of the sums of each band.
    For a single band image, a scalar, or a vector, returns a scalar.
    The uncertainty is pooled differently as this is a sum. The variance will be the variance of
    the means plus the sum of the variances (still following
    Rudmin, J. W. (2010). Calculating the exact pooled variance. arXiv preprint arXiv:1007.1012).

    Pixels with "bad" DQ bits will be ignored.

    @param val:img,number:value to process
    """

    def sum_of_variances(n, u):
        # we calculate variance of the values in the set
        varianceOfMeans = n.var()
        # we calculate the sum of the variances (not the mean this time!)
        sumOfVariances = np.sum(u ** 2)
        # and return the sum of those two.
        return np.sqrt(varianceOfMeans + sumOfVariances)

    rr = stats_wrapper(val,
                       lambda n, u, d: (np.sum(n), sum_of_variances(n, u), pcot.dq.NOUNCERTAINTY))
    return rr


@datumfunc
def flipv(img):
    """
    Flip an image vertically
    @param img:img:image to flip
    """
    img = img.get(Datum.IMG)
    if img is not None:
        return Datum(Datum.IMG, img.flip(vertical=True))
    else:
        return None


@datumfunc
def fliph(img):
    """
    Flip an image horizontally
    @param img:img:image to flip
    """
    img = img.get(Datum.IMG)
    if img is not None:
        return Datum(Datum.IMG, img.flip(vertical=False))
    else:
        return None


@datumfunc
def rotate(img, angle):
    """
    Rotate an image anti-clockwise by an angle in degrees. The angle must be
    a multiple of 90 degrees.

    @param img:img:image to rotate
    @param angle:number:angle to rotate by
    """
    img = img.get(Datum.IMG)
    if img is None:
        return None
    angle = angle.get(Datum.NUMBER).n
    # only permit multiples of 90 degrees, giving an error otherwise
    if angle % 90 != 0:
        raise XFormException('DATA', 'rotation angle must be a multiple of 90 degrees')

    img = img.rotate(angle)
    return Datum(Datum.IMG, img)


@datumfunc
def striproi(img, stripannots=0):
    """
    Strip all regions of interest from an image
    @param img:img:image to strip
    @param stripannots:number:if nonzero, also strip annotations (e.g. colourmap legends) (default is 0)
    """

    img: ImageCube = img.get(Datum.IMG)
    if img is None:
        return None
    img = img.shallowCopy()
    img.rois = []
    if stripannots.get(Datum.NUMBER).n:
        img.annotations = []
    return Datum(Datum.IMG, img)


@datumfunc
def norm(img, splitchans=0):
    """
    normalize all channels of an image to 0-1, operating on all channels combined (the default) or separately
    @param img:img:the image to process
    @param splitchans:number:if nonzero, process each channel separately
    """
    img = img.get(Datum.IMG)
    if img is None:
        return None
    splitchans = splitchans.get(Datum.NUMBER).n
    subimage = img.subimage()
    # the middle argument is whether we're actually clamping. I know, sorry.
    nom, unc, dq = operations.norm.norm(subimage, 0, splitchans)
    img = img.modifyWithSub(subimage, nom, uncertainty=unc, dqv=dq)
    return Datum(Datum.IMG, img)


@datumfunc
def clamp(img):
    """
    clamp all channels of an image to 0-1
    @param img:img:the image to process
    """
    img = img.get(Datum.IMG)
    if img is None:
        return None
    subimage = img.subimage()
    nom, unc, dq = operations.norm.norm(subimage, 1)
    img = img.modifyWithSub(subimage, nom, uncertainty=unc, dqv=dq)
    return Datum(Datum.IMG, img)


@datumfunc
def curve(img, mul=1, add=0):
    """
    impose a sigmoid curve on an image, y=1/(1+e^-(m(x-0.5)+a))) where m and a are parameters. Note
    from that equation that x is biased, so that x=0.5 is the inflection point if c=0.

    @param img:img:the image to process
    @param mul:number:multiply each pixel by this before processing
    @param add:number:add this to each pixel after multiplication
    """
    img = img.get(Datum.IMG)
    if img is None:
        return None
    subimage = img.subimage()
    nom, unc, dq = operations.curve.curve(subimage, mul.get(Datum.NUMBER).n, add.get(Datum.NUMBER).n)
    img = img.modifyWithSub(subimage, nom, uncertainty=unc, dqv=dq)
    return Datum(Datum.IMG, img)


@datumfunc
def resize(img, width, height, method="linear"):
    """
    Resize an image to a new size using OpenCV's resize function. The method is one of:
    "nearest", "linear", "cubic", "area", "lanczos4"
    mapping to the OpenCV constants
    cv2.INTER_NEAREST, cv2.INTER_LINEAR, cv2.INTER_CUBIC, cv2.INTER_AREA, cv2.INTER_LANCZOS

    @param img:img:the image to resize
    @param width:number:the new width
    @param height:number:the new height
    @param method:string:the interpolation method (nearest, linear, cubic, area, lanczos4)
    """
    img = img.get(Datum.IMG)
    if img is None:
        return None
    width = int(width.get(Datum.NUMBER).n)
    height = int(height.get(Datum.NUMBER).n)
    method = method.get(Datum.STRING)

    try:
        method = {
            "nearest": cv.INTER_NEAREST,
            "linear": cv.INTER_LINEAR,
            "cubic": cv.INTER_CUBIC,
            "area": cv.INTER_AREA,
            "lanczos4": cv.INTER_LANCZOS4
        }[method]
    except KeyError:
        raise XFormException('DATA', 'invalid interpolation method')

    img = img.resize(width, height, method)
    return Datum(Datum.IMG, img)


@datumfunc
def interp(img, factor, w=-1):
    """
    Using trilinear interpolation, generate an image by interpolating between the bands of an existing image.
    If an ROI is attached, the image generated will be interpolated from the pixels in the ROI. The width of the image
    will be either given in an optional parameter, or will be the same as the input image.

    WARNING - IS VERY SLOW


    @param img:img:the image to interpolate - the bands must be in ascending wavelength order
    @param factor:number:the "wavelength" we want to generate an image for
    @param w:number:optional width of the image to generate
    """
    img = img.get(Datum.IMG)
    if img is None:
        return None

    width = int(w.get(Datum.NUMBER).n)
    if width < 0:
        width = img.w
    # calculate height, keeping the aspect ratio the same
    height = int(img.h * (width / img.w))

    # get the ROI if present, otherwise the whole image
    if img.rois is None or len(img.rois) == 0:
        rect = Rect(0, 0, img.w, img.h)
    else:
        r = ROI.roiUnion(img.rois)
        if r is None:
            rect = Rect(0, 0, img.w, img.h)
        else:
            rect = r.bb()

    # now get the wavelengths in the image
    wavelengths = [img.wavelength(i) for i in range(img.channels)]
    if len(wavelengths) < 2:
        raise XFormException('DATA', 'image must have at least two bands to interpolate')
    # fail if any are -1
    if any([x == -1 for x in wavelengths]):
        raise XFormException('DATA', 'image must have wavelength data to interpolate')
    # ensure they are monotonic
    if not all([x < y for x, y in zip(wavelengths, wavelengths[1:])]):
        raise XFormException('DATA', 'image wavelengths must be in ascending order')

    # get the interpolation value, which will be a wavelength
    factor = factor.get(Datum.NUMBER).n

    # construct the volume - the x and y coordinates are those of the image, the z coordinate is the wavelength
    x_volume = np.arange(img.w)
    y_volume = np.arange(img.h)
    z_volume = np.array(wavelengths)

    # the volume is the image data
    volume = img.img
    # create the destination array
    outimg = np.zeros((height, width), dtype=np.float32)

    import pcot.utils.interp as ip

    with Timer("interp"):
        # perform the interpolation; an expensive operation!
        xfactor = rect.w / width
        yfactor = rect.h / height
        for x in range(width):
            for y in range(height):
                xx = x * xfactor + rect.x
                yy = y * yfactor + rect.y
                outimg[y, x] = ip.trilinear_interpolation_fast(y_volume, x_volume, z_volume, volume, yy, xx, factor)
            print(x)
    # construct the new imagecube
    img = ImageCube(outimg, None, img.sources, uncertainty=None, dq=None)

    return Datum(Datum.IMG, img)


@datumfunc
def reducecircles(img, thresh, useratio=0):
    """
    Given an image with a set of circular ROIs, reduce all the radii until the maximum of the pooled SDs of
    the bands stops decreasing. The threshold value "thresh" is the value by which the SD must stop decreasing
    before we stop reducing the radius. This is useful for finding the smallest circle around a region of the same value.


    Alternatively, if an optional boolean is set, we just reduce every circle by a given ratio.

    @param img:img:the image to process
    @param thresh:number:the pooled SD threshold, or the ratio if the useratio flag is set
    @param useratio:number:if non-zero use the max of the means rather than the max of pooled SDs
    """

    img1 = img.get(Datum.IMG)
    thresh = thresh.get(Datum.NUMBER).n

    if img1 is None:
        return None

    useratio = useratio.get(Datum.NUMBER).n > 0.1  # ignore warning due to wrappers

    def getsd(img, r):
        """get the maximum pooled SD of the pixels in an ROI across all bands"""
        s = img.subimage(roi=r)
        # split the image into bands
        ns, us = s.masked_all(maskBadPixels=True, noDQ=True)
        ns = image.imgsplit(ns)
        us = image.imgsplit(us)
        # calculate the pooled SD for each band
        bandsds = [pooled_sd(nn, uu) for nn, uu in zip(ns, us)]
        # and get the maximum across all bands
        return np.max(bandsds)

    # make a copy of the ROIs, we'll work on these
    rs = [x.copy() for x in img1.rois]

    # for each ROI, we reduce until the SD has stopped decreasing

    for r in rs:
        if not isinstance(r, ROICircle):
            raise XFormException('DATA', 'reducecircles: ROIs must be circles')

        if useratio:
            # we want to reduce the radius by a ratio
            r.r = int(r.r * thresh)
            if r.r < 1:
                r.r = 1
        else:
            prev = None
            while True:
                current = getsd(img1, r)  # get SD of ROI
                # we exit if the SD has stopped decreasing by n or we've hit the minimum radius
                if prev is not None and (prev - current < thresh or r.r == 1):
                    break
                prev = current
                logger.debug(f"reducecircles: ROI {r.label}, {r.r} SD/mean {current}")
                r.r -= 1

    # OK, now output the image with the new ROIs
    img1.rois = rs
    return Datum(Datum.IMG, img1)


@datumfunc
def valuesbyfilter(img):
    """
    Rather like the spectrum node, this gathers together all the pixel values for an ROI. However, it just
    outputs them in a table by filter, not by frequency. Useful for collating certain kinds of calibration
    data.

    @param img:img:the image to process
    """
    img = img.get(Datum.IMG)
    if img is None:
        return None

    d = dict()  # the dictionary of roi -> {filtername -> (sd,mean)}
    for r in img.rois:
        subimg = img.subimage(roi=r)
        ns, us = subimg.masked_all(True, True)
        ns = image.imgsplit(ns)
        us = image.imgsplit(us)
        # there must be only 1 filter per source
        for sourceSet, n, u in zip(img.sources.sourceSets, ns, us):
            if len(sourceSet.sourceSet) != 1:
                raise XFormException('DATA', 'valuesbyfilter: each band must have exactly one filter')
            f = sourceSet.getOnlyItem().getFilter()
            if f is None:
                raise XFormException('DATA', 'valuesbyfilter: each band must have filter data')
            if r.label not in d:
                d[r.label] = dict()
            if f.name not in d[r.label]:
                d[r.label][f.name] = (np.mean(n), pooled_sd(n, u))
            else:
                raise XFormException('DATA', 'valuesbyfilter: filter appears twice in bands')

    # now output as a table object
    table = Table()
    for k, filtdict in d.items():
        for f, (n, u) in filtdict.items():
            table.newRow()
            table.add("ROI", k)
            table.add("filter", f)
            table.add("n", n)
            table.add("u", u)

    return Datum(Datum.DATA, table, sources=SourceSet(img.sources.getSources()))


@datumfunc
def overlay(img1, img2):
    """Given a pair of images of the same dimensions and band count, replace all pixels in the first
    image with the second EXCEPT where the second image has the NODATA bit set. This is useful for
    combining two images where one image has "holes" (e.g. registration).

    @param img1:img:the image to overlay
    @param img2:img:the overlay image with NODATA bits

    """

    img1 = img1.get(Datum.IMG)
    img2 = img2.get(Datum.IMG)
    if img1 is None or img2 is None:
        return None

    if img1.w != img2.w or img1.h != img2.h or img1.channels != img2.channels:
        raise XFormException('DATA', 'images must have the same dimensions and band count to overlay')

    # combine the source sets
    ss = MultiBandSource.createBandwiseUnion([img1.sources, img2.sources])

    # mask out the NODATA bits
    mask = img2.dq & pcot.dq.NODATA
    # make an image copy and put the combined data into it
    img = img1.copy()
    img.img = np.where(mask, img1.img, img2.img)
    img.uncertainty = np.where(mask, img1.uncertainty, img2.uncertainty)
    # DQ is a bit messier. We want the ORed DQ bits, but we only want NODATA
    # where it's set in BOTH images.
    dq = (img1.dq | img2.dq) & ~NODATA  # remove NODATA from the ORed DQ
    dq |= mask & img1.dq  # add NODATA from img1 where it's set in img2
    img.dq = dq
    return Datum(Datum.IMG, img)


@datumfunc
def getflats(img):
    """
    Given an image with single-channel bands from a known camera, return the flatfield images for each band
    as another image with the same band assignments as the input. The flats will come from the camera data
    for the camera.

    @param img:img:the image to get flats for
    """
    import builtins  # ugh. because I override max above.
    import pcot.cameras

    img = img.get(Datum.IMG)

    # for each band, get a set of filters for the sources of that band, and make sure each band
    # only uses one filter
    filters = img.sources.getFiltersByBand()

    if len(filters) == 0:
        raise XFormException('DATA', 'image must have filter data to get flats')
    if builtins.max([len(x) for x in filters]) != 1:
        raise XFormException('DATA', 'each band must have exactly one filter to get flats')

    # and now just turn into a list of filters by band
    filters = [next(iter(x)) for x in filters]  # ugly idiom for getting only item in set
    logger.debug(f"getflats: Filters are {[x.name for x in filters]}")

    # get the cameras from the camera system. Yes, different bands could conceivably come from
    # different cameras.

    cameras = [x.camera_name for x in filters]
    if any([x is None for x in cameras]):
        raise XFormException('DATA', 'filters must have camera data to get flats')
    logger.debug(f"getflats: Cameras are {cameras}")

    # now we can get the camera objects - will raise exception if not found
    # and we can get the flats - which should be images.
    flats = [pcot.cameras.getCamera(x.camera_name).getFlat(x.name) for x in filters]

    # these should all be single-channel images; we can check that.
    if any([x is None for x in flats]):
        raise XFormException('DATA', 'could not find flatfield images for all bands')
    if any([x.get(Datum.IMG) is None for x in flats]):
        raise XFormException('DATA', 'flatfield images must be images')
    if any([x.get(Datum.IMG).channels != 1 for x in flats]):
        raise XFormException('DATA', 'flatfield images must be single-channel')

    return merge(*flats)


@datumfunc
def stripsources(d):
    """
    Strip all sources from a datum, leaving the data intact. This is sometimes necessary in certain
    processing pipelines e.g. to avoid bands with multiple sources in spectrum nodes.

    @param d:img,number:the data to strip sources from
    """
    if d.tp == Datum.IMG:
        img = d.get(Datum.IMG)
        if img is None:
            return None
        img = img.shallowCopy()
        img.sources = MultiBandSource()
        return Datum(Datum.IMG, img)
    else:
        # we assume it's a number, and just return it as is
        n = d.get(Datum.NUMBER)
        if n is None:
            return None
        return Datum(Datum.NUMBER, n, sources=nullSourceSet)