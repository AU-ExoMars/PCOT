from typing import Tuple, Optional, Union

import numpy as np

from pcot import dq
from pcot.imagecube import SubImageCube

# number of points in lookup table
from pcot.value import Value

NUMPOINTS = 1000
# x-coords of table
lutxcoords = np.linspace(0, 1, NUMPOINTS)


def genLut(m, c):
    """mult by m, add c (with some tweakage)"""
    xb = m * (lutxcoords - 0.5) + c
    lut = (1.0 / (1.0 + np.exp(-xb)))
    return lut


# noinspection PyUnreachableCode
def doCurve(m, c, subimage: SubImageCube, lut):
    newimg = subimage.masked().copy()
    newimg = np.interp(newimg, lutxcoords, lut).astype(np.float32)

    # UNCERTAINTY COMMENTED OUT for speed reasons, but this *should* work.

    # uncertainty calculated by plugging 1/(1+exp(m*(x-0.5)+c)) into https://astro.subhashbose.com/tools/error-propagation-calculator
    if False:
        masked = subimage.maskedUncertainty().copy()
        n = np.cosh((c + m*(newimg-0.5))/2)**4
        n = (unc * np.sqrt((m**2) / n))/4
        np.putmask(newunc, mask, n)
        newdqs = dq
    else:
        newunc = subimage.uncertainty.copy()
        mask = subimage.fullmask()
        newunc[mask] = 0
        newdqs = subimage.dq.copy()
        newdqs[mask] |= dq.NOUNCERTAINTY
    return newimg, newunc, newdqs


def curve(subimage: SubImageCube, mul: Union[Value, float], add: Union[Value, float]) -> \
        Tuple[np.array, np.array, np.array]:
    # TODO UNCERTAINTY
    mul = mul.n if isinstance(mul, Value) else mul
    add = add.n if isinstance(add, Value) else add
    lut = genLut(mul, add)

    newsubimg, newunc, newdq = doCurve(mul, add, subimage, lut)

    return newsubimg, newunc, newdq
