import builtins

import cv2 as cv
import numpy as np

import pcot.dq
from pcot import rois, operations
from pcot.config import getAssetPath
from pcot.datum import Datum
from pcot.expressions.register import funcWrapper, statsWrapper, datumfunc
from pcot.expressions.ops import combineImageWithNumberSources
from pcot.filters import Filter
from pcot.imagecube import ImageCube
from pcot.rois import ROI
from pcot.sources import MultiBandSource, SourceSet, Source
from pcot.utils import image
from pcot.utils.deb import Timer
from pcot.utils.geom import Rect
from pcot.utils.maths import pooled_sd
from pcot.value import Value, add_sub_unc_list
from pcot.xform import XFormException


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
    # We don't want to inadvertently recurse, so call the builtin
    # abs function.
    return funcWrapper(lambda xx: builtins.abs(xx), a)


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

    def concat(xx,dtype):
        """Take a list of mixed scalar and 1D numpy arrays. Concatenate into
        a single 1D numpy array."""
        es = [np.array([e],dtype=dtype) if np.isscalar(e) else e for e in xx]
        return np.concatenate(es)

    ns = concat([x.n for x in values],np.float32)
    us = concat([x.u for x in values],np.float32)
    dqs = concat([x.dq for x in values],np.uint16)

    # now build our value
    return Datum(Datum.NUMBER, Value(ns,us,dqs), sources=SourceSet([x.sources for x in args]))




testImageCache = {}


@datumfunc
def testimg(index):
    """
    Load a test image
    @param index : number : the index of the image to load
    """
    fileList = ("marsRGB.png", "gradRGB.png")
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
    dq = np.where(data <= mn, pcot.dq.ERROR, 0).astype(np.uint16)
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
    img.sources = MultiBandSource([Source().setBand(Filter(float(cwl), 30, 1.0, idx=0))])
    return Datum(Datum.IMG, img)


@datumfunc
def flatmean(val, *args):
    """
    find the mean±sd of the values of a set of images and/or scalars.
    Uncertainties in the data will be pooled. Images will be flattened into a list of values,
    so the result for multiband images may not be what you expect.

    @param val:img,number:value(s) to input
    """
    v = (val,) + args
    return statsWrapper(lambda n, u: Value(np.mean(n), pooled_sd(n, u), pcot.dq.NONE), v)


@datumfunc
def min(val, *args):
    """
    find the minimum of the nominal values of a set of images and/or scalars.
    Images will be flattened into a list of values,
    so the result for multiband images may not be what you expect.

    @param val:img,number:value(s) to input
    """
    v = (val,) + args
    return statsWrapper(lambda n, u: Value(np.min(n), 0, pcot.dq.NOUNCERTAINTY), v)


@datumfunc
def max(val, *args):
    """
    find the maximum of the nominal values of a set of images and/or scalars.
    Images will be flattened into a list of values,
    so the result for multiband images may not be what you expect.

    @param val:img,number:value(s) to input
    """
    v = (val,) + args
    return statsWrapper(lambda n, u: Value(np.max(n), 0, pcot.dq.NOUNCERTAINTY), v)


@datumfunc
def sum(val, *args):
    """
    find the sum of the values of a set of images and/or scalars.
    Images will be flattened into a list of values,
    so the result for multiband images may not be what you expect.

    @param val:img,number:value(s) to input
    """
    v = (val,) + args
    return statsWrapper(lambda n, u: Value(np.sum(n), add_sub_unc_list(u), pcot.dq.NONE), v)


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
def striproi(img):
    """
    Strip all regions of interest from an image
    @param img:img:image to strip
    """
    img: ImageCube = img.get(Datum.IMG)
    if img is None:
        return None
    img = img.shallowCopy()
    img.rois = []
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
        rect = Rect(0,0, img.w, img.h)
    else:
        r = ROI.roiUnion(img.rois)
        if r is None:
            rect = Rect(0,0, img.w, img.h)
        else:
            rect = r.bb()

    # now get the wavelengths in the image
    wavelengths = [img.wavelength(i) for i in range(img.channels)]
    if len(wavelengths)<2:
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
                xx = x*xfactor + rect.x
                yy = y*yfactor + rect.y
                outimg[y, x] = ip.trilinear_interpolation_fast(y_volume, x_volume, z_volume, volume, yy, xx, factor)
            print(x)
    # construct the new imagecube
    img = ImageCube(outimg, None, img.sources, uncertainty=None, dq=None)

    return Datum(Datum.IMG, img)