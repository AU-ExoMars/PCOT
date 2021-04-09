## binary operations which work on many kinds of data sensibly.
from typing import Any, Callable

import numpy as np

import conntypes
from pancamimage import ImageCube
from xform import Datum, XFormException


# The problem with binary operation NODES is that we have to set an output type:
# ANY is no use. So in this, we have to check that the type being generated is
# correct.

def binop(a: Datum, b: Datum, op: Callable[[Any, Any], Any], outType: conntypes.Type) -> Datum:
    # if either input is None, the output will be None
    if a is None or b is None:
        return None

    # if either input is an image, the output will be an image, so check the output type
    # is correct.
    if outType != conntypes.IMG and (a.isImage() or b.isImage()):
        raise XFormException('DATA', 'Output type must be image if either input is image')

    if a.isImage() and b.isImage():
        # get actual images
        imga = a.val.img
        imgb = b.val.img
        # check images are same size/depth
        if imga.shape != imgb.shape:
            raise XFormException('DATA', 'Images must be same shape')
        # perform calculation
        img = op(imga, imgb)  # will generate a numpy array
        # generate the image
        r = Datum(conntypes.IMG, ImageCube(img, sources=ImageCube.buildSources([a.val, b.val])))
    elif a.tp == conntypes.NUMBER and b.isImage():
        # here, we're combining a number with an image to give an image
        # which will have the same sources
        img = op(a.val, b.val.img)
        r = Datum(conntypes.IMG, ImageCube(img, sources=b.val.sources))
    elif a.isImage() and b.tp == conntypes.NUMBER:
        # same as previous case, other way round
        img = op(a.val.img, b.val)
        r = Datum(conntypes.IMG, ImageCube(img, sources=a.val.sources))
    elif a.tp == conntypes.NUMBER and b.tp == conntypes.NUMBER:
        # easy case:  op(number,number)->number
        r = Datum(conntypes.NUMBER, op(a.val, b.val))

    return r
