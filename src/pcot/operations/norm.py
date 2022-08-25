# Normalize the image to the 0-1 range. The range is taken across all channels if splitchans is False,
# otherwise the image is split into channels, each is normalised, and then the channels are reassembled.
# If mode is 1, we clip to 0-1 rather than normalizing
from typing import Optional, Tuple

import numpy as np

import pcot.utils.image as image
from pcot.imagecube import SubImageCubeROI
from pcot.xform import XFormException


def _norm(masked: np.ma.masked_array):
    # get min and max
    mn = masked.min()
    mx = masked.max()
    if mn == mx:
        # just set the error and return an empty image
        raise XFormException("DATA", "cannot normalize, image is a single value")
    # otherwise Do The Thing, only using the masked region
    res = (masked - mn) / (mx - mn)
    return res


def norm(img: SubImageCubeROI, clip: int, splitchans=False) -> np.array:
    """Does both normalisation and clipping depending on the clip value (integer boolean because it's used in expr nodes)"""
    mask = img.fullmask()  # get mask with same shape as below image
    img = img.img  # get imagecube bounded by ROIs as np array

    # get the part of the image we are working on
    masked = np.ma.masked_array(img, mask=~mask)
    # make a working copy
    cp = img.copy()

    if clip == 0:  # normalize mode
        if splitchans == 0:
            res = _norm(masked)
        else:
            res = image.imgmerge([_norm(x) for x in image.imgsplit(img)])
    else:  # clip
        # do the thing, only using the masked region
        masked[masked > 1] = 1
        masked[masked < 0] = 0
        res = masked

    # overwrite the changed result into the working copy
    np.putmask(cp, mask, res)
    return cp
