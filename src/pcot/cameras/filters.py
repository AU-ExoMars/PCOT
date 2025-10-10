import csv
import math
import os.path
from pathlib import Path
from typing import List

import numpy as np
from skimage.data import camera

from pcot import ui
from pcot.documentsettings import DocumentSettings
import logging

"""This file deals with the physical multispectral filters"""


logger = logging.getLogger(__name__)


class Filter:
    """The filter class describes a single filter's parameters"""
    # centre wavelength
    cwl: float
    # full-width at half-maximum
    fwhm: float
    # transmission ratio
    transmission: float
    # position of filter in camera (L/R+number for WAC)
    position: str
    # name of filter (e.g. G01 for "geology 1") (if not given, will be str(cwl))
    name: str
    # camera name
    camera_name: str
    # description of the camera - a short phrase
    description: str
    # filter response wavelengths, a numpy array of float32
    wavelengths: np.ndarray
    # filter response values, a numpy array of float32 of the same length as wavelengths
    response: np.ndarray

    def __init__(self, cwl, fwhm, transmission=1.0, position=None, name=None, camera_name=None, description=None,
                 wavelengths=None, response=None):
        """constructor"""
        self.cwl = cwl
        self.fwhm = fwhm
        self.transmission = transmission
        self.name = name if name is not None else str(cwl)
        self.position = position
        self.camera_name = camera_name
        self.description = description
        self.wavelengths = wavelengths
        self.response = response
        if self.wavelengths is not None or self.response is not None:
            if self.wavelengths is None or self.response is None:
                raise ValueError("Filter wavelengths and response arrays must both be present or both be absent")
            if len(self.wavelengths) != len(self.response):
                raise ValueError("Filter wavelengths and response arrays must be the same length")
            if len(self.wavelengths) < 2:
                raise ValueError("Filter wavelengths and response arrays must have at least 2 elements")

    def __hash__(self):
        """The hash of a filter is its name. This is here because we want to be able to
        use a filter as a key in a dictionary."""
        return hash(self.name)

    def __eq__(self, other):
        """Two filters are equal if their members are equal."""
        if not isinstance(other, Filter):
            return False
        return vars(self) == vars(other)

    def hasMissingData(self):
        """True if the filter has missing data (i.e. no cwl)"""
        return self.cwl is None or self.cwl == 0

    def serialise(self):
        return self.cwl, self.fwhm, self.transmission, self.position, \
               self.name, self.camera_name

    @classmethod
    def deserialise(cls, d):
        # various legacy tests here.
        if isinstance(d, str):
            ui.error("Oops - old style file contains filter name, not filter data. Using dummy, please 'Run All'.")
            return DUMMY_FILTER

        # we might have to deserialise a truncated tuple for legacy code
        defaults = [None, None, 1.0, "unknown pos", "no name", "unknown camera", "no description"]
        d = d + defaults[len(d):]
        cwl, fwhm, trans, pos, name, camname, desc = d
        return Filter(cwl, fwhm, trans, pos, name, camname, desc)

    def simulate(self, wavelengths: np.ndarray) -> np.ndarray:
        """Simulate a Gaussian filter profile with the given centre wavelength, full-width at half-maximum
        and transmission. Return the values at the given wavelengths."""
        sigma = self.fwhm / (2 * np.sqrt(2 * np.log(2)))
        values = self.transmission * np.exp(-0.5 * ((wavelengths - self.cwl) / sigma) ** 2)
        return values

    def getResponse(self, wavelengths: np.ndarray) -> np.ndarray:
        """Get the filter response at the given wavelengths. If the filter has a response curve, use that,
        otherwise simulate a Gaussian."""
        if self.wavelengths is not None and self.response is not None:
            return np.interp(wavelengths, self.wavelengths, self.response, left=0, right=0)
        else:
            return self.simulate(wavelengths)

    def getCaption(self, captionType=DocumentSettings.CAP_DEFAULT):
        """Format according to caption type"""
        if captionType == DocumentSettings.CAP_POSITIONS:  # 0=Position
            cap = self.position
        elif captionType == DocumentSettings.CAP_NAMES:  # 1=Name
            cap = self.name
        elif captionType == DocumentSettings.CAP_CWL:  # 2=Wavelength
            cap = str(int(self.cwl))
        else:
            cap = f"CAPBUG-{captionType}"  # if this appears captionType is out of range.
        return cap

    def sourceDesc(self):
        """Description used in Source long descriptions"""
        return f"Cam: {self.camera_name}, Filter: {self.name}({self.cwl}nm) pos {self.position}, {self.description}"

    def __repr__(self):
        return f"Filter({self.name},{self.cwl}@{self.fwhm}, {self.position}, t={self.transmission})"


def wav2RGB(wavelength, scale=1.0):
    """This is  VERY CRUDE wavelength to RGB converter, for visualisation use only!
    Originally from an algorithm in FORTRAN by Dan Bruton.
    http://www.physics.sfasu.edu/astro/color/spectra.html
    """
    w = int(wavelength)

    # colour
    if 380 <= w < 440:
        R = -(w - 440.) / (440. - 350.)
        G = 0.0
        B = 1.0
    elif 440 <= w < 490:
        R = 0.0
        G = (w - 440.) / (490. - 440.)
        B = 1.0
    elif 490 <= w < 510:
        R = 0.0
        G = 1.0
        B = -(w - 510.) / (510. - 490.)
    elif 510 <= w < 580:
        R = (w - 510.) / (580. - 510.)
        G = 1.0
        B = 0.0
    elif 580 <= w < 645:
        R = 1.0
        G = -(w - 645.) / (645. - 580.)
        B = 0.0
    elif 645 <= w <= 780:
        R = 1.0
        G = 0.0
        B = 0.0
    else:
        R = 0.0
        G = 0.0
        B = 0.0

    # intensity correction
    if 380 <= w < 420:
        SSS = 0.3 + 0.7 * (w - 350) / (420 - 350)
    elif 420 <= w <= 700:
        SSS = 1.0
    elif 700 < w <= 780:
        SSS = 0.3 + 0.7 * (780 - w) / (780 - 700)
    else:
        SSS = 0.0
    SSS *= scale

    return [(SSS * R), (SSS * G), (SSS * B)]


## dummy filter for when we have trouble finding the value
DUMMY_FILTER = Filter(0, 0, 1.0, "??", "??")
