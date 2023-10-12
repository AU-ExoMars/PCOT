import csv
import math
from pathlib import Path
from typing import List

import numpy as np

from pcot import ui

"""This file deals with the physical multispectral filters"""


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

    def __init__(self, cwl, fwhm, transmission=1.0, position=None, name=None, idx=0):
        """constructor"""
        self.cwl = cwl
        self.fwhm = fwhm
        self.transmission = transmission
        self.name = name if name is not None else str(cwl)
        self.position = position

    def serialise(self):
        return self.cwl, self.fwhm, self.transmission, self.position, \
               self.name

    @classmethod
    def deserialise(cls, d):
        if isinstance(d, str):  # snark
            ui.error("Oops - old style file contains filter name, not filter data. Using dummy, please reload input.")
            return Filter(2000, 1.0, 1.0, "dummypos", "dummyname", 0)
        try:
            cwl, fwhm, trans, pos, name = d
        except ValueError:
            ui.error("Oops - old style file wrong number of filter data. Using dummy, please reload input.")
            return Filter(2000, 1.0, 1.0, "dummypos", "dummyname", 0)

        cwl, fwhm, trans, pos, name = d
        return Filter(cwl, fwhm, trans, pos, name)

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

_filterSets = {}

def loadFilterSet(name: str, path: Path):
    """Load a filter set from a file and store in the internal dict"""

    def decomment(csvfile):  # comments are like those in Python
        for row in csvfile:
            raw = row.split('#')[0].strip()
            if raw:
                yield raw

    # build a list of filters
    filters = []
    with open(path) as file:
        for r in csv.DictReader(decomment(file)):
            f = Filter(int(r['cwl']),
                       int(r['fwhm']),
                       float(r['transmission']),
                       r['position'],
                       r['name'])
            filters.append(f)
    # and store that in a dictionary of filter set name -> filter list
    _filterSets[name] = filters


def saveFilters(path: str, filters: List[Filter]):
    """save a filter set - used in debugging and development"""
    fields = ('cwl', 'fwhm', 'transmission', 'position', 'name')
    with open(path, "w", newline='') as file:
        w = csv.DictWriter(file, fields)
        w.writeheader()
        for f in filters:
            # extract the fields from the filter objects
            d = {k: getattr(f, k) for k in fields}
            # get a bit more precision on the floats
            d = {k: format(v, ".6g") if isinstance(v, float) else v for k, v in d.items()}
            w.writerow(d)


def getFilter(filterset, target, search='name'):
    if filterset not in _filterSets:
        raise Exception(f"cannot find filter set {filterset}")

    # a simple linear search is plenty fast enough here. We can search on name, pos or cwl.
    if search == 'name':
        for x in _filterSets[filterset]:
            if x.name == target:
                return x
    elif search == 'pos':
        for x in _filterSets[filterset]:
            if x.position == target:
                return x
    elif search == 'cwl':
        for x in _filterSets[filterset]:
            if x.cwl == target:
                return x
    return DUMMY_FILTER


def getFilterSetNames():
    """return the names of all the filter sets we know about"""
    return _filterSets.keys()


## dummy filter for when we have trouble finding the value
DUMMY_FILTER = Filter(0, 0, 0, "??", "??")
