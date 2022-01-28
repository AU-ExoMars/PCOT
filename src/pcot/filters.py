import math
from typing import Tuple

import numpy as np

"""This file deals with the physical multispectral filters for the PANCAM and AUPE cameras"""


class Filter:
    """The filter class describes a single filter's parameters"""
    # centre wavelength
    cwl: float
    # full-width at half-maximum
    fwhm: float
    # transmission ratio
    transmission: float
    # position of filter in camera (L/R+number)
    position: str
    # name of filter (e.g. G01 for "geology 1")
    name: str
    # camera type (PANCAM or AUPE)
    camera: str
    # index in array, used for certain visualisations (e.g. PDS4 timeline)
    idx: int

    def __init__(self, cwl, fwhm, transmission, position=None, name=None, camera=None):
        """constructor"""
        self.cwl = cwl
        self.fwhm = fwhm
        self.transmission = transmission
        self.name = name if name is not None else str(cwl)
        self.position = position
        # typically set later
        self.camera = camera
        self.idx = 0


    @staticmethod
    def _gaussian(x, mu, fwhm):
        """calculate the value of a normal distribution at x, where mu is the mean
        and fwhm is full width at half max."""
        def fwhm_to_sigma(fwhm_):
            return fwhm_ / (2 * math.sqrt(2 * math.log(2)))  # ~= 2.35482

        return np.exp(-(x - mu) ** 2 / (2 * fwhm_to_sigma(fwhm) ** 2))

    def response_over(self, x: np.ndarray):
        """generate a response curve from an input array of frequencies (I think)"""
        return self._gaussian(x, self.cwl, self.fwhm)


def wav2RGB(wavelength):
    """This is  VERY CRUDE wavelength to RGB converter, for visualisation use only!
    Originally from an algorithm in FORTRAN by Dan Bruton."""
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
    #    SSS *= 255

    return [(SSS * R), (SSS * G), (SSS * B)]


## Array of Pancam filters - data from Coates, A. J., et al. "The PanCam instrument for the ExoMars rover." Astrobiology 17.6-7 (2017): 511-541
PANCAM_FILTERS = [
    Filter(570, 12, .989, "L01", "G04"),
    Filter(530, 15, .957, "L02", "G03"),
    Filter(610, 10, .956, "L03", "G05"),
    Filter(500, 20, .966, "L04", "G02"),
    Filter(670, 12, .962, "L05", "G06"),
    Filter(440, 25, .987, "L06", "G01"),
    Filter(640, 100, .993, "L07", "C01L"),
    Filter(540, 80, .988, "L08", "C02L"),
    Filter(440, 120, .983, "L09", "C03L"),
    Filter(925, 5, 0.000000552, "L10", "S01"),
    Filter(935, 5, 0.000000854, "L11", "S02"),

    Filter(840, 25, .989, "R01", "G09"),
    Filter(780, 20, .981, "R02", "G08"),
    Filter(740, 15, .983, "R03", "G07"),
    Filter(900, 30, .983, "R04", "G10"),
    Filter(950, 50, .994, "R05", "G11"),
    Filter(1000, 50, .996, "R06", "G12"),
    Filter(640, 100, .993, "R07", "C01R"),
    Filter(540, 80, .988, "R08", "C02R"),
    Filter(440, 120, .983, "R09", "C03R"),
    Filter(450, 5, 0.000001356, "R10", "S03"),
    Filter(670, 5, 0.000000922, "R11", "S04")
]

for i, x in enumerate(PANCAM_FILTERS):
    x.camera = 'PANCAM'
    x.idx = i

## Array of AUPE filters - I've added the lower-case letters myself;
# they were all G0 or G1
AUPE_FILTERS = [
    Filter(440, 120, 1, "L01", "C03L"),
    Filter(540, 80, 1, "L02", "C02L"),
    Filter(640, 100, 1, "L03", "C01L"),

    Filter(438, 24, 1, "L04", "G0a"),
    Filter(500, 24, 1, "L05", "G0b"),
    Filter(532, 10, 1, "L06", "G0c"),
    Filter(568, 10, 1, "L07", "G0d"),
    Filter(610, 10, 1, "L08", "G0e"),
    Filter(671, 10, 1, "L09", "G0f"),
    Filter(425, 25, 1, "L10", "G0g"),
    Filter(400, 50, 1, "L11", "G0h"),

    Filter(440, 120, 1, "R01", "C03R"),
    Filter(540, 80, 1, "R02", "C02R"),
    Filter(640, 100, 1, "R03", "C01R"),

    Filter(740, 13, 1, "R04", "G1a"),
    Filter(780, 37, 1, "R05", "G1b"),
    Filter(832, 10, 1, "R06", "G1c"),
    Filter(900, 50, 1, "R07", "G1d"),
    Filter(950, 50, 1, "R08", "G1e"),
    Filter(1000, 50, 1, "R09", "G1f"),

    Filter(525, 50, 1, "R10", "GUESS"),  # THIS IS A GUESS
]

for i, x in enumerate(AUPE_FILTERS):
    x.camera = 'AUPE'
    x.idx = i


## dummy filter for when we have trouble finding the value
DUMMY_FILTER = Filter(0, 0, 0, "??", "??", camera='PANCAM')

## dictionary of AUPE filters by position (L/R+number)
AUPEfiltersByPosition = {x.position: x for x in AUPE_FILTERS}

## dictionary of AUPE filters by name - e.g. G01 (geology 1),
# C01L (colour 1 left)
AUPEfiltersByName = {x.name: x for x in AUPE_FILTERS}

## dictionary of PANCAM filters by position (L/R+number)
PANCAMfiltersByPosition = {x.position: x for x in PANCAM_FILTERS}

## dictionary of PANCAM filters by name - e.g. G01 (geology 1),
# C01L (colour 1 left)
PANCAMfiltersByName = {x.name: x for x in PANCAM_FILTERS}


def getFilterByPos(fpos, aupe=False):
    """Return a filter given its position string, used in multifile sources"""
    if aupe:
        d = AUPEfiltersByPosition
    else:
        d = PANCAMfiltersByPosition
    return d[fpos] if fpos in d else DUMMY_FILTER


def findFilter(cameraType: str, name: str) -> Filter:
    """Given a filter's ID, try to find it in either AUPE or PANCAM."""
    if cameraType == 'PANCAM':
        if name in PANCAMfiltersByName:
            f = PANCAMfiltersByName[name]
            return f
    elif cameraType == 'AUPE':
        if name in AUPEfiltersByName:  # yeah, duplication. So sue me.
            f = AUPEfiltersByName[name]
            return f
    else:
        raise Exception(f"unknown camera type {camera}")

    raise Exception(f"Unable to find filter {name} for {camera}")
