"""
Filter response classes, which consist of interpolators

1. FilterResponseSimple encapsulates an interpolator wavelength->response value. These can be generated
   from cwl,fwhm and transmission by simulating a gaussian.
2. FullFilterResponse encapsulates a more complex interpolator; maybe (phi,theta,wavelength)->response value
   Not sure we need it?
"""
import logging
import re
from typing import Optional

import numpy as np
from scipy.interpolate import RegularGridInterpolator

logger = logging.getLogger(__name__)

# the range for generating sinulated data
SIMULATED_FILTER_WAVELENGTHS = np.arange(200, 3500)

class FilterResponse:
    _sim_cache = dict()  # cache for simulated responses
    """
    This describes the stored filter response for a filter where this has been measured (if it's not, the Filter
    class will simulate).
    """

    _interpolator: RegularGridInterpolator
    _is_simulated: bool  # essentially determines if this gets saved to the camera data file.
    clipped_to: Optional[float]

    def __init__(self, interpolator: Optional[RegularGridInterpolator],
                 wavelengths: Optional[np.ndarray]=None,
                 values: Optional[np.ndarray]=None,
                 clipped_to: Optional[float]=None,
                 is_simulated=False):
        """If an interpolator is provided, use it. Otherwise create a simulated interpolator from wavelengths and values."""
        if interpolator is None:
            self._interpolator = RegularGridInterpolator((wavelengths,), values,
                                                     method="linear",
                                                     bounds_error=False,  # no error on out-of-bounds
                                                     fill_value=None)  # we extrapolate the data if out-of-bounds
        else:
            self._interpolator = interpolator
        self._is_simulated = is_simulated
        self.clipped_to = clipped_to   # the level to which this response has been clipped (percentage), or None

    def __str__(self):
        """Used in debugging"""
        dims = "x".join(map(str, self._interpolator.values.shape))
        return f"FilterResponse(sim={self.is_simulated}, interp={dims})"

    def sourceDesc(self):
        """Used in Source descriptions"""
        dims = "x".join(map(str, self._interpolator.values.shape))
        return f"{'sim' if self._is_simulated else 'real'},{dims}"

    @staticmethod
    def createSimulated(cwl: float, fwhm: float, transmission: float):
        """Simulate a Gaussian filter profile with the given centre wavelength, full-width at half-maximum
        and transmission. Return the values at the given wavelengths. We keep a cache of these."""

        key = f"{cwl}/{fwhm}{transmission}"
        if key in FilterResponse._sim_cache:
            return FilterResponse._sim_cache[key]

        if cwl == 0:
            # handle the "dummy filter" response
            values = np.zeros(SIMULATED_FILTER_WAVELENGTHS.shape)
        else:
            sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
            values = transmission * np.exp(-0.5 * ((SIMULATED_FILTER_WAVELENGTHS - cwl) / sigma) ** 2)
        res = FilterResponse(None, wavelengths=SIMULATED_FILTER_WAVELENGTHS, values=values, is_simulated=True)
        FilterResponse._sim_cache[key] = res
        FilterResponse._sim_cache[key] = res
        return res

    def getResponse(self, wavelengths: np.ndarray, angle=0.0) -> np.ndarray:
        dims = len(self._interpolator.values.shape)
        if dims == 1:
            return self._interpolator(wavelengths)
        elif dims == 2:
            return self._interpolator((wavelengths, angle))
        else:
            raise NotImplementedError(f"{dims}-dimensional interpolators not implemented")

    def serialise(self):
        if self._is_simulated:
            # we return None if the filter is simulated - no point in saving that data.
            return None
        else:
            return {
                "points": self._interpolator.grid,
                "values": self._interpolator.values,
                "method": self._interpolator.method,
                "clipped_to": self.clipped_to,
            }

    @staticmethod
    def deserialise(data):
        # this should only be called on a non-simulated filter, because of the check in serialise()
        v = data["values"]
        interp = RegularGridInterpolator(data["points"], v, method=data["method"],
                                         bounds_error=False, fill_value=0.0)
        return FilterResponse(interp, clipped_to=data.get("clipped_to",None))

    @property
    def is_simulated(self):
        return self._is_simulated

    @staticmethod
    def load_from_csv(csv: str, response_percentage=True, response_clip_percentage=None) -> 'FilterResponse':
        """This is only called when we generate filter response data from files in gencam. It parses a filter
        response. The first column is the wavelength, remaining columns are response - if there is more than
        one remaining column, it is assumed to contain an angle (for looking through the filter aslant, as it were;
        not the same angles as we deal with in reflectance!). Otherwise it's just the response at all angles.

        The response_clip_percentage gives a clipping level for responses (we might need this if we get overunity
        responses for certain filters due to sensor mode switching problems). If it is not provided, you'll
        get an error if the responses are over unity. If it is, clipping is done to this level and an error given
        if it was necessary.
        """

        # We're not using the csv package, and we're opening with latin-1 because my data has a degree symbol!

        NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")      # regex for finding first valid number as a group

        def extract_number(s: str):
            m = NUMBER_RE.search(s)
            return m.group(0) if m else None

        with open(csv, encoding="latin-1") as f:
            lines = f.readlines()
            wavelengths = []
            # get the angles if needed from the first line; assume the first column is "wavelength" or something
            header = lines[0]
            angles = [extract_number(x) for x in header.split(",")[1:]]
            if len(angles) == 1:
                # only one angle, and a non-number is OK (and expected) in that slot
                angles = [0.0]
            else:
                # more than one angle, and they have to be numbers
                if any(x is None for x in angles):
                    raise ValueError("A non-numeric angle is provided for a multiangle filter response")
                angles = [float(x) for x in angles]
            lines = lines[1:]  # strip headers
            wavelengths = []
            # each row in this array is data at each wavelength,
            # and consists of values for each angle.
            # In short, rows=wavelengths, cols=angles.
            values_by_angle_by_wavelength = []

            response_factor = 0.01 if response_percentage else 1.0
            for line in lines:
                line = line.strip().split(",")
                wavelengths.append(float(line[0]))
                # Note that the data is PERCENTAGES.
                values = [float(x)*response_factor for x in line[1:]]
                values_by_angle_by_wavelength.append(values)

            values = np.array(values_by_angle_by_wavelength, dtype=np.float32)

            # we have an array of responses, so create an interpolator.
            data = np.stack(values, axis=0)

            # clip the data if we need to
            clipped_to = None
            if response_clip_percentage is not None:
                clip_value = response_clip_percentage/100.0
                if np.any(data > clip_value):
                    logger.warning(f"Some response values are over specified clip {response_clip_percentage}%")
                    data = np.clip(data, 0, clip_value)
                    clipped_to = response_clip_percentage
            elif np.any(data > 1.0):
                    raise ValueError("Some response values are over 1.0 and no response_clip_percentage is provided")

            points = [np.array(x, np.float32) for x in (wavelengths, angles)]
            interpolator = RegularGridInterpolator(points, data,
                                                   bounds_error=False,
                                                   fill_value=0.0
                                                   )
            return FilterResponse(interpolator, clipped_to=clipped_to)



