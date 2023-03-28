from typing import List

import numpy as np


def fit(rho: List[float], signal: List[List[float]]):
    """Function for fitting sets of points to a line using the method in Allender, Elyse J., et al.
    “The ExoMars spectral tool (ExoSpec): An image analysis tool for ExoMars 2020 PanCam imagery.”
    Image and Signal Processing for Remote Sensing XXIV. Vol. 10789.
    International Society for Optics and Photonics, 2018.

    This should be run on all patches, for each filter.

    Inputs:
        - rho: list of lab-measured reflectance readings, one for each patch.
        - signal: for each patch, a set of W.m^2.sr.nm spectral radiance readings from the rover.

    Returns m, c, sdm, sdc

        - m, c : slope and intercept of linear model mapping radiance to reflectance
        - sdm, sdc: uncertainty in the above in standard deviations

    From Gunn, M. Spectral imaging for Mars exploration (Doctoral dissertation, Aberystwyth University).

    """

    # TODO deal with uncertainty!
    # If variables are independent, this could be just aggregating the statistics for each pixel in the ROI
    # by using Chan's batch extension to Welford's algorithm, like this:
    # https://github.com/himbeles/pairwise-statistics

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



