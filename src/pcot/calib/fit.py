from typing import List

import numpy as np
from numpy.typing import NDArray

    
class SimpleValue:
    """Rather than tote a full Value object around we'll use this "cutdown" version which
    just has nominal and uncertainty values and no DQ, and is always an array. This will also
    pool the variances into a single variance by Rudmin's method
    Rudmin, J. W. (2010). Calculating the exact pooled variance. arXiv preprint arXiv:1007.1012"""
    noms: NDArray[np.float32]
    vars: NDArray[np.float32]

    def __init__(self, noms: NDArray[np.float32], stds: NDArray[np.float32]):
        self.noms = noms
        self.vars = stds ** 2
        # and pool the variances - the variance of the entire set of values is the mean of the variances
        # of the individual values plus the variance of the means
        self.var = np.mean(self.vars) + np.var(noms)


def fit(rho: List[float], signals: List[SimpleValue]):
    """Function for fitting sets of points to a line using the method in Allender, Elyse J., et al.
    “The ExoMars spectral tool (ExoSpec): An image analysis tool for ExoMars 2020 PanCam imagery.”
    Image and Signal Processing for Remote Sensing XXIV. Vol. 10789.
    International Society for Optics and Photonics, 2018.

    This should be run for each filter.

    Inputs:
        - rho: list of lab-measured reflectance readings, one for each patch.
        - signal: for each patch, a set of W.m^2.sr.nm spectral radiance readings from the rover.
          In this implementation, this is a list of "simple value" objects, each of which contains two arrays:
            - the nominal value -  mean radiance for each pixel in the patch
            - the uncertainty - the variance of the radiance for each pixel in the patch
          It also contains the pooled variance of the entire set of values, which is calculated from the individual
            variances and the mean values using Rudmin's method and assuming all the pixels were taken from the same
            number of samples.
          Bad pixels should be removed first.

    Returns m, c, sdm, sdc

        - m, c : slope and intercept of linear model mapping radiance to reflectance
        - sdm, sdc: uncertainty in the above in standard deviations

    From Gunn, M. Spectral imaging for Mars exploration (Doctoral dissertation, Aberystwyth University).


    """

    variances = [x.var for x in signals]    # these are the pooled variance for each group of pixels.

    a = sum([1 / x for x in variances])
    b = sum([(r * r) / v for v, r in zip(variances, rho)])
    e = sum([r / v for v, r in zip(variances, rho)])

    delta = a * b - e * e

    d = sum([(r * np.mean(ss.noms)) / v for ss, v, r in zip(signals, variances, rho)])
    f = sum([np.mean(ss.noms) / v for ss, v in zip(signals, variances)])

    m = (a * d - e * f) / delta
    c = (b * f - e * d) / delta

    sdm = np.sqrt(a / delta)
    sdc = np.sqrt(b / delta)

    return m, c, sdm, sdc


def old_fit(rho: List[float], signal: List[List[float]]):
    """Version using lists"""
    # this version calculates the variances up front so we can pool them
    variances = [np.var(ss) for ss in signal]

    a = sum([1 / x for x in variances])
    b = sum([(r * r) / v for v, r in zip(variances, rho)])
    e = sum([r / v for v, r in zip(variances, rho)])

    delta = a * b - e * e

    d = sum([(r * np.mean(ss)) / v for ss, v, r in zip(signal, variances, rho)])
    f = sum([np.mean(ss) / v for ss, v in zip(signal, variances)])

    m = (a * d - e * f) / delta
    c = (b * f - e * d) / delta

    sdm = np.sqrt(a / delta)
    sdc = np.sqrt(b / delta)

    return m, c, sdm, sdc
