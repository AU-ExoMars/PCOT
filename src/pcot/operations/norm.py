# Normalize the image to the 0-1 range. The range is taken across all channels if splitchans is False,
# otherwise the image is split into channels, each is normalised, and then the channels are reassembled.
# If mode is 1, we clip to 0-1 rather than normalizing
from typing import Optional, Tuple

import numpy as np

import pcot.dq
import pcot.utils.image as image
from pcot.imagecube import SubImageCube
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


def norm(subimg: SubImageCube, clamp: int, splitchans=False) -> Tuple[np.array, np.array, np.array]:
    """Does both normalisation and clamping depending on the clamp value (integer boolean because it's used in expr nodes)"""
    mask = subimg.fullmask()  # get mask with same shape as below image
    img = subimg.img  # get imagecube bounded by ROIs as np array

    # make a working copy
    cp = img.copy()
    # get the part of the working copy we are working on
    masked = np.ma.masked_array(cp, mask=~mask)
    # now we can perform operations on "masked", which acts as a slice into "cp"
    dqcopy = None

    if clamp == 0:  # normalize mode
        if splitchans == 0:
            res, scale = _norm(masked)
            unccopy = subimg.uncertainty.copy()
            unc = np.ma.masked_array(unccopy, mask=~mask)
            unc *= scale
        else:
            # split into separate channels - we're going to be using min and max functions,
            # so we need to pass in the masked parts of the image (we want to ignore outside the mask)
            chans = image.imgsplit(masked)
            uncs = image.imgsplit(subimg.uncertainty)

            # this returns a tuple of normalised image and scale factor used to normalise for each channel.
            resAndScales = [_norm(x) for x in chans]
            # which we turn into two separate lists of normalised images and scales
            res, scales = list(zip(*resAndScales))
            # turn the normalised channel images into a single multi-band image
            res = image.imgmerge(res)
            # now we need to scale the uncertainty of each channel using the factor for each
            uncs = [u * s for u, s in zip(uncs, scales)]
            # and merge back into an uncertainty image
            uncs = image.imgmerge(uncs)
            unccopy = subimg.uncertainty.copy()
            # and then write that back into the masked part of the uncertainty image copy
            unccopy[mask] = uncs[mask]

    else:  # clamp
        # do the thing, only using the masked region

        # work out which pixels should be clamped, top and bottom
        top = masked > 1
        bottom = masked < 0
        masked[top] = 1         # do the top clamping
        masked[bottom] = 0      # do the bottom clamping
        res = masked            # and that will be the result

        # we need to clear uncertainty and set NOUNC on clipped data.

        unccopy = subimg.uncertainty.copy()
        unc = np.ma.masked_array(unccopy, mask=~mask)
        unc[top | bottom] = 0

        dqcopy = subimg.dq.copy()
        dq = np.ma.masked_array(dqcopy, mask=~mask)
        dq[top | bottom] |= pcot.dq.NOUNCERTAINTY

    # overwrite the changed result into the working copy
    np.putmask(cp, mask, res)
    return cp, unccopy, dqcopy
