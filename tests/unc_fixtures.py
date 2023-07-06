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


def gen_2b_unc(val0, unc0, val1,  unc1, dq0=0, dq1=0):
    """Generate a 2-channel image with fixed uncertainties and intensities. The image is 20x20 in size"""
    d0, d1, u0, u1 = [np.full((20, 20), x, np.float32) for x in (val0, val1, unc0, unc1)]
    dq0, dq1 = [np.full((20, 20), x, np.uint16) for x in (dq0, dq1)]
    d = np.dstack((d0, d1))
    u = np.dstack((u0, u1))
    dqv = np.dstack((dq0, dq1))
    return ImageCube(d, uncertainty=u, dq=dqv)
