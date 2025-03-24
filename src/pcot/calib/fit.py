from typing import List

import numpy as np
from numpy.typing import NDArray


class SimpleValue:
    """Rather than tote a full Value object around we'll use this "cutdown" version which
    just has nominal and uncertainty values and no DQ, and is always an array. This will also
    pool the variances into a single variance by Rudmin's method
    Rudmin, J. W. (2010). Calculating the exact pooled variance. arXiv preprint arXiv:1007.1012"""
    nom: NDArray[np.float32]
    std: NDArray[np.float32]

    def __init__(self, nom: NDArray[np.float32], std: NDArray[np.float32]):
        self.nom = nom
        self.std = std
        # and pool the variances - the variance of the entire set of values is the mean of the variances
        # of the individual values plus the variance of the means
        self.var = np.mean(std ** 2) + np.var(nom)


def fit_arrays(rho: List[float], signal: List[SimpleValue]):
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
            - the uncertainty - the standard deviation of the radiance for each pixel in the patch
            Bad pixels should be removed first.

    Returns m, c, sdm, sdc

        - m, c : slope and intercept of linear model mapping radiance to reflectance
        - sdm, sdc: uncertainty in the above in standard deviations

    From Gunn, M. Spectral imaging for Mars exploration (Doctoral dissertation, Aberystwyth University).


    """

    # TODO deal with uncertainty!
    # If variables are independent, this could be just aggregating the statistics for each pixel in the ROI
    # by using Chan's batch extension to Welford's algorithm, like this:
    # https://github.com/himbeles/pairwise-statistics

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


def fit(rho: List[float], signal: List[List[float]]):
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


def old_fit(rho: List[float], signal: List[List[float]]):
    """Original code used for comparison while fit() was developed. If the signal values have no uncertainties
    it should produce the same results."""
    a = sum([1 / np.var(ss) for ss in signal])
    b = sum([(r * r) / np.var(ss) for ss, r in zip(signal, rho)])
    e = sum([r / np.var(ss) for ss, r in zip(signal, rho)])

    delta = a * b - e * e

    d = sum([(r * np.mean(ss)) / np.var(ss) for ss, r in zip(signal, rho)])
    f = sum([np.mean(ss) / np.var(ss) for ss in signal])

    m = (a * d - e * f) / delta
    c = (b * f - e * d) / delta

    sdm = np.sqrt(a / delta)
    sdc = np.sqrt(b / delta)

    return m, c, sdm, sdc
