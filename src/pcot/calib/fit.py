"""
This module handles reflectance fitting data. It's up to XFormReflectance to
extract patches from images, while this code actually does the fitting.
XFormReflectance then patches the resulting data into the CalibrationData class
declared here.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from typing import List, Optional, Dict

import numpy as np

from pcot.parameters.taggedaggregates import TaggedDict
from pcot.utils.tabular_provider import TabularProvider, TabularIterator
from pcot.value import Value


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

    def serialise(self):
        return [float(self.mean), float(self.std)]

    @staticmethod
    def deserialise(data) -> SimpleValue:
        mean, std = data
        return SimpleValue(np.float32(mean), np.float32(std))


@dataclasses.dataclass
class ReflectancePoint:
    """A point on the reflectance plot. This is a tuple of two values: the known reflectance and the measured
    reflectance, both stored as SimpleValue objects. The patch name is also stored for labelling purposes.
    """
    known: SimpleValue
    measured: SimpleValue
    sample_count: int
    patch: str

    def serialise(self):
        return {
            "known": self.known.serialise(),
            "measured": self.measured.serialise(),
            "sample_count": int(self.sample_count),
            "patch": self.patch
        }

    @staticmethod
    def deserialise(data) -> ReflectancePoint:
        return ReflectancePoint(SimpleValue.deserialise(data["known"]),
                                SimpleValue.deserialise(data["measured"]),
                                data["sample_count"],
                                data["patch"])


@dataclasses.dataclass
class Fit:
    """The result of a fit. This is a dataclass to make it easier to pass around.
        - m, c : slope and intercept of linear model mapping radiance to reflectance
        - sdm, sdc: uncertainty in the above in standard deviations
        - warning: None, or a string if there may be problems with this fit
    """

    m: float
    c: float
    sdm: float
    sdc: float

    # warning field is not initialised; it's calculated in the post init.
    warning: Optional[str] = dataclasses.field(init=False)

    def __post_init__(self):
        """calculate extra attributes"""
        warns = []
        if self.m < 0:
            warns.append("negative gradient")
        elif self.m <= 0.001:
            warns.append("very small gradient")

        # distance from origin
        d = np.abs(self.c)/np.sqrt(self.m*self.m+1)
        if d > 0.1:
            warns.append("line is far from origin")

        self.warning = None if len(warns) == 0 else ",".join(warns)

    def serialise(self):
        # the warning isn't stored; it's recalculated from the other fields on deserialisation
        return {"m": float(self.m), "c": float(self.c), "sdm": float(self.sdm), "sdc": float(self.sdc)}

    @staticmethod
    def deserialise(data) -> Fit:
        return Fit(data["m"], data["c"], data["sdm"], data["sdc"])




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

    Returns a Fit object; see above.

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


@dataclasses.dataclass
class CalibrationData:
    """
    Data for reflectance calibration - must be JSON-serialisable although numpy arrays are permitted
    """

    # the camera name or None if not yet set
    camera: Optional[str] = dataclasses.field(default=None)

    # the canonical order of the filters - this is a list of filter
    # names as they were in the image from which this was created.
    # None if not set yet.
    filters: Optional[List[str]] = dataclasses.field(default=None)

    # keys are filter _names_. If these dicts are None then we haven't yet done
    # a fit.

    # fits for each filter
    fits: Optional[Dict[str, Fit]] = dataclasses.field(default=None)
    # For each filter, there will be a list of points to fit (and plot). Each point will have
    # the known reflectance and the measured reflectance.
    points_per_filter: Optional[Dict[str, List[ReflectancePoint]]] = dataclasses.field(default=None)
    # filter wavelengths for convenience; we could conceivably check with these to make sure PCOT
    # has the same values when it gets data for these filters using its camera data system.
    cwls: Optional[Dict[str, float]] = dataclasses.field(default=None)

    # these are recorded here in the calibration data but are actually
    # node parameters.
    simpler_data_fudge: bool = dataclasses.field(default=False)
    zero_fudge: bool = dataclasses.field(default=False)

    def valid(self):
        """True if all necessary fields are present, False otherwise"""
        return bool(self.camera and self.filters and self.fits and self.points_per_filter)

    def missingFits(self) -> List[str]:
        """The names of the filters which have no fit (e.g. because the band was bad in every patch).
        Empty if there are no fits at all, because then nothing has been fitted yet."""
        if not self.filters or self.fits is None:
            return []
        return [name for name in self.filters if name not in self.fits]

    # ser and deser methods. We can't use dataclasses.asdict() because it doesn't
    # handle the non-dataclass SimpleValues inside the points, or numpy scalars, and
    # deserialising would leave the fits and points as dicts.

    def serialise(self):
        return {
            "camera": self.camera,
            "filters": self.filters,
            "fits": None if self.fits is None else {k: v.serialise() for k, v in self.fits.items()},
            "points_per_filter": None if self.points_per_filter is None else
                {k: [p.serialise() for p in v] for k, v in self.points_per_filter.items()},
            "cwls": None if self.cwls is None else {k: float(v) for k, v in self.cwls.items()},
            "simpler_data_fudge": self.simpler_data_fudge,
            "zero_fudge": self.zero_fudge,
        }

    @staticmethod
    def deserialise(data) -> CalibrationData:
        fits = data.get("fits")
        ppf = data.get("points_per_filter")
        return CalibrationData(
            camera=data.get("camera"),
            filters=data.get("filters"),
            fits=None if fits is None else {k: Fit.deserialise(v) for k, v in fits.items()},
            points_per_filter=None if ppf is None else
                {k: [ReflectancePoint.deserialise(p) for p in v] for k, v in ppf.items()},
            cwls=data.get("cwls"),
            simpler_data_fudge=data.get("simpler_data_fudge", False),
            zero_fudge=data.get("zero_fudge", False),
        )

    def tabularProvider(self):
        return CalibrationData.Provider(self)

    def getGradientsAndIntercepts(self):
        """return tuple of two vector Values (m,c) in filter order, or (None, None) if the data
        isn't complete (including when any filter has no fit)"""
        if not self.valid() or self.missingFits():
            return None, None
        # get the fits for each filter in order
        fits = [self.fits[name] for name in self.filters]
        # extract gradient and intercept values
        gradient_out_n = [f.m for f in fits]
        gradient_out_u = [f.sdm for f in fits]
        intercept_out_n = [f.c for f in fits]
        intercept_out_u = [f.sdc for f in fits]
        # assemble Value object
        m = Value(np.array(gradient_out_n),np.array(gradient_out_u))
        c = Value(np.array(intercept_out_n),np.array(intercept_out_u))
        return m, c


    class Provider(TabularProvider):
        data: CalibrationData
        def __init__(self ,data: CalibrationData):
            self.data = data

        def getParams(self) -> Optional[TaggedDict]:
            return None

        def getHeaders(self) -> List[str]:
            return ["filter","wavelength (nm)", "m", "m stddev","c","c stddev","warning"]

        def __iter__(self) -> TabularIterator:
            return CalibrationData.Provider.RowIterator(self)

        class RowIterator(TabularIterator):
            provider: CalibrationData.Provider
            iter: Iterator

            def __init__(self, provider: CalibrationData.Provider):
                self.provider = provider
                self.iter = iter(provider.data.filters or [])

            def __next__(self) -> Dict[str, str]:
                rowkey = next(self.iter) # throws StopIteration when it runs out

                data = self.provider.data
                wavelength = f"{data.cwls[rowkey]:g}" if data.cwls and rowkey in data.cwls else ""
                fit = data.fits.get(rowkey) if data.fits else None
                if fit is None:
                    # this filter has no fit, so show the row but without values
                    return {"filter": rowkey, "wavelength (nm)": wavelength,
                            "m": "", "m stddev": "", "c": "", "c stddev": "",
                            "warning": "no fit"}
                return {
                    "filter": rowkey,
                    "wavelength (nm)": wavelength,
                    "m": f"{fit.m:g}",
                    "m stddev": f"{fit.sdm:g}",
                    "c": f"{fit.c:g}",
                    "c stddev": f"{fit.sdc:g}",
                    "warning": fit.warning or ""
                }
