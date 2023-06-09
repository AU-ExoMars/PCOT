from typing import Tuple, Optional, Union

import numpy as np
import cv2 as cv

from pcot.imagecube import SubImageCubeROI

# number of points in lookup table
from pcot.utils import image
from pcot.value import OpData

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


def curve(subimage: SubImageCubeROI, mul: Union[OpData, float], add: Union[OpData, float]) -> np.array:
    # TODO UNCERTAINTY
    mul = mul.n if isinstance(mul, OpData) else mul
    add = add.n if isinstance(add, OpData) else add
    lut = genLut(mul, add)

    if subimage.channels == 1:
        newsubimg = doCurve(subimage.img, subimage.mask, lut)
    else:
        newsubimg = image.imgmerge([doCurve(x, subimage.mask, lut) for x in image.imgsplit(subimage.img)])

    return newsubimg
