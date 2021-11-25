## binary operations which work on many kinds of data sensibly.
from typing import Any, Callable, Optional

import numpy as np

from pcot.datum import Datum, Type
from pcot.imagecube import ImageCube
from pcot.rois import BadOpException
from pcot.sources import MultiBandSource, SourceSet


class BinopException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


def twoImageBinop(imga: ImageCube, imgb: ImageCube, op: Callable[[Any, Any], Any]) -> ImageCube:
    # check images are same size/depth
    if imga.img.shape != imgb.img.shape:
        raise BinopException('Images must be same shape in binary operation')
    # if imga has an ROI, use that for both. Similarly, if imgb has an ROI, use that.
    # But if they both have a subimage they must be the same.
    ahasroi = imga.hasROI()
    bhasroi = imgb.hasROI()
    if ahasroi or bhasroi:
        if ahasroi and bhasroi:
            rois = imga.rois
            subimga = imga.subimage()
            subimgb = imgb.subimage()
            if subimga.bb != subimgb.bb:  # might need an extra check on the masks - but what would it be?
                raise BinopException('regions of interest must be the same size in binary operation')
        else:
            # get subimages, using their own image's ROI if it has one, otherwise the other image's ROI.
            # One of these will be true.
            rois = imga.rois if ahasroi else imgb.rois
            subimga = imga.subimage(None if ahasroi else imgb)
            subimgb = imgb.subimage(None if bhasroi else imga)

        maskeda = subimga.masked()
        maskedb = subimgb.masked()
        # get masked subimages
        # perform calculation and get result subimage
        ressubimg = op(maskeda, maskedb)  # will generate a numpy array
        # splice that back into a copy of image A, but just take its image, because we're going to
        # rebuild the sources
        img = imga.modifyWithSub(subimga, ressubimg).img
    else:
        # neither image has a roi
        img = op(imga.img, imgb.img)
        rois = None

    sources = MultiBandSource.createBandwiseUnion([imga.sources, imgb.sources])
    outimg = ImageCube(img, sources=sources)
    if rois is not None:
        outimg.rois = rois.copy()
    return Datum(Datum.IMG, outimg)


def combineImageWithNumberSources(img: ImageCube, other: SourceSet) -> MultiBandSource:
    """This is used to generate the source sets when an image is combined with something else,
    e.g. an image is multiplied by a number. In this case, each band of the image is combined with
    the other sources."""
    x = [x.sourceSet for x in img.sources.sourceSets]

    return MultiBandSource([SourceSet(x.sourceSet.union(other.sourceSet)) for x in img.sources.sourceSets])


# The problem with binary operation NODES is that we have to set an output type:
# ANY is no use. So in this, we have to check that the type being generated is
# correct. Of course, in an expression we don't do that.

def binop(a: Datum, b: Datum, op: Callable[[Any, Any], Any], outType: Optional[Type]) -> Datum:
    # if either input is None, the output will be None
    if a is None or b is None:
        return None

    # if either input is an image, the output will be an image, so check the output type
    # is correct. But only do the check if there IS an output type.

    if outType is not None and outType != Datum.IMG and (a.isImage() or b.isImage()):
        raise BinopException('Output type must be image if either input is image')

    if a.isImage() and a.val is None:
        raise BinopException("Cannot perform binary operation on None image")
    if b.isImage() and b.val is None:
        raise BinopException("Cannot perform binary operation on None image")

    if a.isImage() and b.isImage():
        r = twoImageBinop(a.val, b.val, op)
    elif a.tp == Datum.NUMBER and b.isImage():
        # here, we're combining a number with an image to give an image
        # which will have the same sources
        img = b.val
        subimg = img.subimage()
        img = img.modifyWithSub(subimg, op(a.val, subimg.masked()))
        img.rois = b.val.rois.copy()
        img.sources = combineImageWithNumberSources(img, a.getSources())
        r = Datum(Datum.IMG, img)
    elif a.isImage() and b.tp == Datum.NUMBER:
        # same as previous case, other way round
        img = a.val
        subimg = img.subimage()
        img = img.modifyWithSub(subimg, op(subimg.masked(), b.val))
        img.rois = a.val.rois.copy()
        img.sources = combineImageWithNumberSources(img, b.getSources())
        r = Datum(Datum.IMG, img)
    elif a.tp == Datum.NUMBER and b.tp == Datum.NUMBER:
        # easy case:  op(number,number)->number
        r = Datum(Datum.NUMBER, op(a.val, b.val), SourceSet([a.getSources(), b.getSources()]))
    elif a.tp == Datum.ROI and b.tp == Datum.ROI:
        # again, easy case because ROI has most operations overloaded. Indeed, those that aren't valid
        # will fail.
        try:
            r = Datum(Datum.ROI, op(a.val, b.val), SourceSet([a.getSources(), b.getSources()]))
        except BadOpException as e:
            raise BinopException("unimplemented operation for ROIs")
    else:
        raise BinopException("incompatible types for operator")

    return r


def unop(a: Datum, op: Callable[[Any], Any], outType: Optional[Type]) -> Datum:
    if a is None:
        return None

    if outType is not None and outType != Datum.IMG and a.isImage():
        raise BinopException('Output type must be image if input is image')

    if a.isImage():
        img = a.val
        if img.hasROI():
            subimg = img.subimage()
            masked = subimg.masked()
            ressubimg = op(masked)
            rimg = img.modifyWithSub(subimg, ressubimg).img
        else:
            rimg = op(img.img)
        out = ImageCube(rimg, sources=img.sources)  # originally this built a new source set. Don't know why.
        out.rois = img.rois.copy()
        r = Datum(Datum.IMG, out)
    elif a.tp == Datum.NUMBER:
        r = Datum(Datum.NUMBER, op(a.val), a.getSources())
    else:
        raise BinopException("bad type type for unary operator")

    return r
