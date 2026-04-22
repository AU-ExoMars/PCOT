"""
Tests of filter loading, and simulation if necessary
"""
import logging
import os

import numpy as np
import pytest

from pcot import config, cameras
from pcot.sources import Source
from pcot.cameras.camdata import CameraData

logger = logging.getLogger(__name__)


def load():
    """Try to load the training geology camera for testing"""
    path = config.getDefaultDir('cameras')
    if path is None:
        pytest.fail("Camera directory not set")

    path = os.path.expanduser(path)
    logger.debug(f"Loading camera data from {path}")
    cam = CameraData(path + "/training1_geol.parc")
    return cam


def test_filterload():
    """Requires the TRAINING_GEOLOGY camera to be in the cameras file. Make sure it has
    appropriate response data."""

    cam = load()

    f = cam.getFilter("G01")
    assert f is not None
    assert not f.response.is_simulated  # make sure it's real data

    r = f.getResponse(399,12)  # get response at 399nm, 12 degrees
    # looked up in the original table of percentages
    assert np.isclose(r, 0.009909)

    # check another one at a different angle for the same wavelength
    r = f.getResponse(399,18)
    assert np.isclose(r, 0.01141)
    r = f.getResponse(399,19)  # interpolation required
    assert np.isclose(r, 0.01160)

    # check OOB
    r = f.getResponse(100,20)
    assert r==0.0
    r = f.getResponse(10000,20)
    assert r==0.0

    # check OOB
    r = f.getResponse(400,89)
    assert r==0.0
    r = f.getResponse(400,-1)
    assert r==0.0
