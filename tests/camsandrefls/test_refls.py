import numpy as np
import pytest

import pcot
from pcot import config
from pcot.cameras import reflectances
from pcot.cameras.reflectances import Reflectance


def test_pct_reflectance():
    """We're not going to test the data itself here - we can't - but we can check a few things.
    This test will "xfail" - fail but lightly - if the data is not present"""
    config.loadReflectances()
    try:
        refl:Reflectance = pcot.cameras.getReflectance("PCT")
    except pcot.cameras.ReflectanceNotFoundException:
        pytest.xfail("Reflectance not found")
    # let's get some data for phi=0, theta=0
    with pytest.raises(KeyError):
        # Check that unknown patches raise an error
        refl.get_reflectances("QUOP", 0, 0, 0)

    # grab the data ranges
    phi_range, theta_range, w_range = refl.get_range("NG11")
    print( phi_range, theta_range, w_range)

    # check that single wavelength value fetches are extrapolated outside the theta range
    inrange = refl.get_reflectances("NG11",180, -80, 1000)
    outofrange = refl.get_reflectances("NG11", 180, -90, 1000)
    # we can't do this accurately, but we do know that it should be lower!
    assert outofrange < inrange

    # same goes for wavelengths.
    inrange = refl.get_reflectances("NG11",180, 0, 400)
    outofrange = refl.get_reflectances("NG11", 180, 0, 200)
    assert outofrange < inrange

    # check we can get all the wavelengths, that the result is a tuple of 1D arrays,
    # and that the arrays have the same shape.
    wvls = refl.get_reflectances("NG11",180, 0)
    assert len(wvls[0].shape)==1
    assert np.array_equal(wvls[0].shape,wvls[1].shape)

    # try getting a subset of wavelengths
    wvls = refl.get_reflectances("NG11",180, 0, [500, 600, 700])
    assert len(wvls.shape)==1
    assert wvls.shape[0] == 3
    assert np.all(wvls < 0.9) # make sure the results look like valid reflectances!