import math
import numpy as np


## @package filters
# This package deals with the physical multispectral filters for the PANCAM and AUPE cameras

## The filter class describes a single filter's parameters
class Filter:
    ## @var cwl
    # centre wavelength
    cwl: float
    ## @var fwhm
    # full-width at half-maximum
    fwhm: float
    ## @var transmission
    # transmission ratio
    transmission: float
    ## @var position
    # position of filter in camera (L/R+number)
    position: str
    ## @var name
    # name of filter (e.g. G01 for "geology 1")
    name: str

    ## constructor
    def __init__(self, cwl, fwhm, transmission, position=None, name=None):
        self.cwl = cwl
        self.fwhm = fwhm
        self.transmission = transmission
        self.name = name if name is not None else str(cwl)
        self.position = position

    @staticmethod
    def _gaussian(x, mu, fwhm):
        def fwhm_to_sigma(fwhm):
            return fwhm / (2 * math.sqrt(2 * math.log(2)))  # ~= 2.35482

        return np.exp(-(x - mu) ** 2 / (2 * fwhm_to_sigma(fwhm) ** 2))

    ## generate a response curve from an input array of frequencies (I think)
    def response_over(self, x: np.ndarray):
        return self._gaussian(x, self.cwl, self.fwhm)


## Array of Pancam filters - note: solar filters omitted
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
    Filter(840, 25, .989, "R01", "G09"),
    Filter(780, 20, .981, "R02", "G08"),
    Filter(740, 15, .983, "R03", "G07"),
    Filter(900, 30, .983, "R04", "G10"),
    Filter(950, 50, .994, "R05", "G11"),
    Filter(1000, 50, .996, "R06", "G12"),
    Filter(640, 100, .993, "R07", "C01R"),
    Filter(540, 80, .988, "R08", "C02R"),
    Filter(440, 120, .983, "R09", "C03R"),
]

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
]

## dummy filter for when we have trouble finding the value
DUMMY_FILTER = Filter(0, 0, 0, "??", "??")

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
