# Normalize the image to the 0-1 range. The range is taken across all channels if splitchans is False,
# otherwise the image is split into channels, each is normalised, and then the channels are reassembled.
# If mode is 1, we clip to 0-1 rather than normalizing
from typing import Optional, Tuple

import numpy as np

import pcot.dq
import pcot.utils.image as image
from pcot.imagecube import SubImageCubeROI
from pcot.xform import XFormException


def _norm(masked: np.ma.masked_array) -> Tuple[np.array, float]:
    """returns normalized array and scaling factor (to modify uncertainty)"""
    # get min and max
    mn = masked.min()
    mx = masked.max()
    if mn == mx:
        # just set the error and return an empty image
        raise XFormException("DATA", "cannot normalize, image is a single value")
    # otherwise Do The Thing, only using the masked region
    scale = 1.0 / (mx - mn)
    res = (masked - mn) * scale
    return res, scale


def norm(subimg: SubImageCubeROI, clamp: int, splitchans=False) -> Tuple[np.array, np.array, np.array]:
    """Does both normalisation and clamping depending on the clamp value (integer boolean because it's used in expr nodes)"""
    mask = subimg.fullmask()  # get mask with same shape as below image
    img = subimg.img  # get imagecube bounded by ROIs as np array

    # get the part of the image we are working on

    masked = np.ma.masked_array(img, mask=~mask)
    # make a working copy
    cp = img.copy()

    if clamp == 0:  # normalize mode
        if splitchans == 0:
            res, scale = _norm(masked)
        else:
            res, scale = image.imgmerge([_norm(x) for x in image.imgsplit(img)])
        # now we need to scale the uncertainty
        unccopy = subimg.uncertainty.copy()
        unc = scale * np.ma.masked_array(subimg.uncertainty, mask=~mask)
        np.putmask(unccopy, mask, unc)
    else:  # clamp
        # do the thing, only using the masked region
        top = masked > 1
        bottom = masked < 0
        masked[top] = 1
        masked[bottom] = 0
        res = masked
        # we need to clear uncertainty and set NOUNC on clipped data.
        unccopy = subimg.uncertainty.copy()
        unc = np.ma.masked_array(subimg.uncertainty, mask=~mask)
        unc[top | bottom] = 0
        np.putmask(unccopy, mask, unc)
        dqcopy = subimg.dq.copy()
        dq = np.ma.masked_array(subimg.dq, mask=~mask)
        dq[top | bottom] |= pcot.dq.NOUNCERTAINTY
        np.putmask(dqcopy, mask, dq)

        unccopy = None  # uncertainty unchanged

    # overwrite the changed result into the working copy
    np.putmask(cp, mask, res)
    return cp, unccopy, None
