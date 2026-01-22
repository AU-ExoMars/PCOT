"""
Filter response classes, which consist of interpolators

1. SimpleFilterResponse encapsulates an interpolator wavelength->response value. These can be generated
   from cwl,fwhm and transmission by simulating a gaussian.
2. FullFilterResponse encapsulates an interpolator (phi,theta,wavelength)->response value
"""


import numpy as np
from scipy.interpolate import RegularGridInterpolator

# the range for generating sinulated data
SIMULATED_FILTER_WAVELENGTHS = np.arange(200, 3500)


class FilterResponse:
    """FilterResponses work on this interface - for simple filters the angle is ignored"""

    def getResponse(self, wavelengths: np.ndarray, angle=0.0) -> np.ndarray:
        """Get the filter response at the given wavelengths."""
        raise Exception("Base type of FilterResponse created - deserialised a Filter without patching in a response?")


class FilterResponseSimple(FilterResponse):
    _sim_cache = dict()  # cache for simulated responses
    """
    This describes the stored filter response for a filter where this has been measured (if it's not, the Filter
    class will simulate).
    """

    def __init__(self, wavelengths: np.ndarray, values: np.ndarray):
        self._interpolator = RegularGridInterpolator((wavelengths,), values,
                                                     method="linear",
                                                     bounds_error=False,  # no error on out-of-bounds
                                                     fill_value=None)  # we extrapolate the data if out-of-bounds

    @staticmethod
    def createSimulated(cwl: float, fwhm: float, transmission: float):
        """Simulate a Gaussian filter profile with the given centre wavelength, full-width at half-maximum
        and transmission. Return the values at the given wavelengths. We keep a cache of these."""

        key = f"{cwl}/{fwhm}{transmission}"
        if key in FilterResponseSimple._sim_cache:
            return FilterResponseSimple._sim_cache[key]

        if cwl == 0:
            # handle the "dummy filter" response
            values = np.zeros(SIMULATED_FILTER_WAVELENGTHS.shape)
        else:
            sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
            values = transmission * np.exp(-0.5 * ((SIMULATED_FILTER_WAVELENGTHS - cwl) / sigma) ** 2)
        res = FilterResponseSimple(SIMULATED_FILTER_WAVELENGTHS, values)
        FilterResponseSimple._sim_cache[key] = res
        return res

    def getResponse(self, wavelengths: np.ndarray, angle=0.0) -> np.ndarray:
        return self._interpolator(wavelengths)



