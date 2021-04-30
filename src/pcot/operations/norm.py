# Normalize the image to the 0-1 range. The range is taken across all three channels.
from typing import Optional, Tuple

import numpy as np

from pcot.pancamimage import SubImageCubeROI
from pcot.xform import XFormException


def norm(img: SubImageCubeROI, mode: int) -> np.array:

    mask = img.fullmask()       # get mask with same shape as below image
    img = img.img               # get imagecube bounded by ROIs as np array

    # get the part of the image we are working on
    masked = np.ma.masked_array(img, mask=~mask)
    # make a working copy
    cp = img.copy()
    # get min and max
    mn = masked.min()
    mx = masked.max()
    # by default, the returned exception is None
    ex = None

    if mode == 0:  # normalize mode
        if mn == mx:
            # just set the error and return an empty image
            raise XFormException("DATA", "cannot normalize, image is a single value")
        else:
            # otherwise Do The Thing, only using the masked region
            res = (masked - mn) / (mx - mn)
    elif mode == 1:  # clip
        # do the thing, only using the masked region
        masked[masked > 1] = 1
        masked[masked < 0] = 0
        res = masked

    # overwrite the changed result into the working copy
    np.putmask(cp, mask, res)
    return cp
