import numpy as np

import builtins
from pcot import rois
import pcot.dq
from pcot.config import getAssetPath
from pcot.datum import Datum
from pcot.expressions.builtins import funcWrapper
from pcot.expressions.datumfuncs import datumfunc
from pcot.expressions.ops import combineImageWithNumberSources
from pcot.imagecube import ImageCube
from pcot.sources import MultiBandSource, SourceSet
from pcot.utils import image
from pcot.value import Value
from pcot.xform import XFormException
import cv2 as cv


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

            # uncertainty is messier - add the squared uncertainties, divide by N, and root.
            outu = np.zeros(img.uncertainty.shape[:2], dtype=np.float32)
            for i in range(0, img.channels):
                c = img.uncertainty[:, :, i]
                outu += c * c
            # divide by the count and root
            outu = np.sqrt(outu) / img.channels
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
    create a 3-channel image consisting of the current RGB mapping of the input image
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
    return funcWrapper(lambda xx: xx.sin(), a)


@datumfunc
def cos(a):
    """
    Calculate cosine of an angle in radians
    @param a:img,number:the angle (or image in which each pixel is a single angle)
    """
    return funcWrapper(lambda xx: xx.cos(), a)


@datumfunc
def tan(a):
    """
    Calculate tangent of an angle in radians
    @param a:img,number:the angle (or image in which each pixel is a single angle)
    """
    return funcWrapper(lambda xx: xx.tan(), a)


@datumfunc
def sqrt(a):
    """
    Calculate square root
    @param a:img,number:values (image or number)
    """
    return funcWrapper(lambda xx: xx.sqrt(), a)


@datumfunc
def abs(a):     # careful now, we're shadowing the builtin "abs" here.
    """
    Calculate absolute value
    @param a:img,number:values (image or number)
    """
    # this is really ugly, but it avoids the damn thing recursing
    # and lets us still call it abs.
    return funcWrapper(lambda xx: builtins.abs(xx), a)


testImageCache = {}


@datumfunc
def testimg(index):
    """
    Load a test image
    @param index : number : the index of the image to load
    """
    fileList = ("test1.png",)
    n = int(index.get(Datum.NUMBER).n)
    if n < 0:
        raise XFormException('DATA', 'negative test file index')
    n %= len(fileList)

    global testImageCache
    if n in testImageCache:
        img = testImageCache[n]
    else:
        try:
            p = getAssetPath(fileList[n])
        except FileNotFoundError as e:
            raise XFormException('DATA', f"cannot find test image{fileList[n]}")
        img = ImageCube.load(p, None, None)
        testImageCache[n] = img

    return Datum(Datum.IMG, img)


