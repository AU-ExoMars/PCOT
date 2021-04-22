from typing import Tuple, Optional

import numpy as np
import cv2 as cv

# number of points in lookup table
from pancamimage import SubImageCubeROI
from xform import XFormException

NUMPOINTS = 1000
# x-coords of table
lutxcoords = np.linspace(0, 1, NUMPOINTS)


def genLut(mul, add):
    xb = mul * (lutxcoords - 0.5) + add
    lut = (1.0 / (1.0 + np.exp(-xb)))
    return lut


def doCurve(img, mask, lut):
    masked = np.ma.masked_array(img, mask=~mask)
    cp = img.copy()
    np.putmask(cp, mask, np.interp(masked, lutxcoords, lut).astype(np.float32))
    return cp


def curve(subimage: SubImageCubeROI, mul: float, add: float) -> np.array:
    lut = genLut(mul, add)

    if subimage.channels == 1:
        newsubimg = doCurve(subimage.img, subimage.mask, lut)
    else:
        newsubimg = cv.merge([doCurve(x, subimage.mask, lut) for x in cv.split(subimage.img)])

    return newsubimg
