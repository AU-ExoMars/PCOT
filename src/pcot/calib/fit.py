import dataclasses
from typing import List

import numpy as np
from numpy.typing import NDArray

    
class SimpleValue:
    mean: np.float32
    var: np.float32     # variance, not standard deviation
    std: np.float32

    def __init__(self, mean: np.float32, std: np.float32):
        self.mean = mean
        self.std = std
        self.var = std * std

    def __repr__(self):
        return f"SimpleValue({self.mean}±{self.std})"


@dataclasses.dataclass
class Fit:
    """The result of a fit. This is a dataclass to make it easier to pass around."""
    m: float
    c: float
    sdm: float
    sdc: float


def fit(rho: List[SimpleValue], signals: List[SimpleValue]) -> Fit:
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

    measured_vars = [x.var for x in signals]    # these are the pooled variances for each group of pixels (each patch).
    measured_means = [x.mean for x in signals]  # the mean for each patch

    # We are currently ignoring the uncertainties in the reference values, which is a simplification.

    rho = [x.mean for x in rho]  # the reflectance values for each patch

    a = sum([1 / x for x in measured_vars])
    b = sum([(r * r) / v for v, r in zip(measured_vars, rho)])
    e = sum([r / v for v, r in zip(measured_vars, rho)])
    delta = a * b - e * e

    d = sum([(r * m) / v for v, r, m in zip(measured_vars, rho, measured_means)])
    f = sum([m / v for v, m in zip(measured_vars, measured_means)])

    m = (a * d - e * f) / delta
    c = (b * f - e * d) / delta

    sdm = np.sqrt(a / delta)
    sdc = np.sqrt(b / delta)

    return Fit(m, c, sdm, sdc)
