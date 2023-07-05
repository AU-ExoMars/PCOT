"""Fixtures and functions for generating uncertainty test data"""

import numpy as np
import pytest

from pcot.imagecube import ImageCube
from pcot.utils.image import imgmerge


def gen_mono_unc(val, unc):
    """generate a mono image with a fixed uncertainty and intensity throughout.
    The image is 20x20 in size."""
    data = np.full((20, 20), val, np.float32)
    uncd = np.full((20, 20), unc, np.float32)
    return ImageCube(data, uncertainty=uncd)


def gen_2b_unc(val1, unc1, val2,  unc2):
    """Generate a 2-channel image with fixed uncertainties and intensities. The image is 20x20 in size"""
    d1, d2, u1, u2 = [np.full((20, 20), x, np.float32) for x in (val1, val2, unc1, unc2)]
    d = np.dstack((d1, d2))
    u = np.dstack((u1, u2))
    return ImageCube(d, uncertainty=u)
