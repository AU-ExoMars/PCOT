## binary operations which work on many kinds of data sensibly.
from typing import Any, Callable

import numpy as np

import pcot.conntypes as conntypes
from pcot.pancamimage import ImageCube
from pcot.xform import Datum, XFormException


class BinopException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


# The problem with binary operation NODES is that we have to set an output type:
# ANY is no use. So in this, we have to check that the type being generated is
# correct. Of course, in an expression we don't do that.

def binop(a: Datum, b: Datum, op: Callable[[Any, Any], Any], outType: conntypes.Type) -> Datum:
    # if either input is None, the output will be None
    if a is None or b is None:
        return None

    # if either input is an image, the output will be an image, so check the output type
    # is correct. But only do the check if there IS an output type.

    if outType is not None and outType != conntypes.IMG and (a.isImage() or b.isImage()):
        raise BinopException('Output type must be image if either input is image')

    if a.isImage() and b.isImage():
        # get actual images
        imga = a.val
        imgb = b.val
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

        outimg = ImageCube(img, sources=ImageCube.buildSources([a.val, b.val]))
        if rois is not None:
            outimg.rois = rois.copy()
        r = Datum(conntypes.IMG, outimg)
    elif a.tp == conntypes.NUMBER and b.isImage():
        # here, we're combining a number with an image to give an image
        # which will have the same sources
        img = b.val
        subimg = img.subimage()
        img = img.modifyWithSub(subimg, op(a.val, subimg.masked()))
        img.rois = b.val.rois.copy()
        r = Datum(conntypes.IMG, img)
    elif a.isImage() and b.tp == conntypes.NUMBER:
        # same as previous case, other way round
        img = a.val
        subimg = img.subimage()
        img = img.modifyWithSub(subimg, op(subimg.masked(), b.val))
        img.rois = a.val.rois.copy()
        r = Datum(conntypes.IMG, img)
    elif a.tp == conntypes.NUMBER and b.tp == conntypes.NUMBER:
        # easy case:  op(number,number)->number
        r = Datum(conntypes.NUMBER, op(a.val, b.val))
    else:
        raise BinopException("incompatible types for operator")

    return r


def unop(a: Datum, op: Callable[[Any],Any], outType: conntypes.Type) -> Datum:
    if a is None:
        return None

    if outType is not None and outType != conntypes.IMG and a.isImage():
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
        out = ImageCube(rimg, sources=ImageCube.buildSources([img]))
        out.rois = img.rois.copy()
        r = Datum(conntypes.IMG, out)
    elif a.tp == conntypes.NUMBER:
        r = Datum(conntypes.NUMBER, op(a.val))
    else:
        raise BinopException("bad type type for unary operator")

    return r