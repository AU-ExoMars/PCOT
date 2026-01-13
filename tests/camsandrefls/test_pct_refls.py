"""We're not going to test the data itself here - we can't - but we can check a few things.
This test will "xfail" - fail but lightly - if the data is not present"""
import numpy as np
import pytest

import pcot
from pcot import config
from pcot.cameras import reflectances
from pcot.cameras.reflectances import Reflectance

def load():
    config.loadReflectances()
    try:
        return pcot.cameras.getReflectance("PCT")
    except pcot.cameras.ReflectanceNotFoundException:
        pytest.xfail("Reflectance not found")

def test_pct_reflectance_bad_patch():
    # let's get some data for phi=0, theta=0
    refl = load()
    with pytest.raises(KeyError):
        # Check that unknown patches raise an error
        refl.get_reflectances("QUOP", 0, 0)

def test_pct_reflectance_single_val_extrapolate_theta():
    refl = load()
    # check that single wavelength value fetches are extrapolated outside the theta range
    inrange = refl.get_reflectance("NG11",180, -80, 1000)
    outofrange = refl.get_reflectance("NG11", 180, -90, 1000)
    # we can't do this accurately, but we do know that it should be lower!
    assert outofrange < inrange

def test_pct_reflectance_single_val_extrapolate_w():
    # same goes for interpolating wavelengths out of range.
    refl = load()
    inrange = refl.get_reflectances("NG11",180, 0, 400)
    outofrange = refl.get_reflectances("NG11", 180, 0, 200)
    assert outofrange < inrange

def test_pct_reflectance_get_all():
    # check we can get all the wavelengths, that the result is a tuple of 1D arrays,
    # and that the arrays have the same shape.
    refl = load()
    wvls = refl.get_reflectances("NG11",180, 0)
    assert len(wvls[0].shape)==1
    assert np.array_equal(wvls[0].shape,wvls[1].shape)

def test_pct_reflectance_get_subset_list():
    # try getting a subset of wavelengths as a list
    refl = load()
    wvls = refl.get_reflectances("NG11",180, 0, [500, 600, 700])
    assert len(wvls.shape)==1
    assert wvls.shape[0] == 3
    assert np.all(wvls < 0.9) # make sure the results look like valid reflectances!

def test_pct_reflectance_get_subset_nparray():
    # try getting a subset of wavelengths with nparray
    refl = load()
    wvls = refl.get_reflectances("NG11",180, 0, np.array([500, 600, 700]))
    assert len(wvls.shape)==1
    assert wvls.shape[0] == 3
    assert np.all(wvls < 0.9) # make sure the results look like valid reflectances!

def test_pct_reflectance_get_subset_agree():
    # check that all three methods agree - getting using list, nparray, and individual vals
    refl = load()
    wvls1 = refl.get_reflectances("NG11",180, 0, np.array([500, 600, 700]))
    wvls2 = refl.get_reflectances("NG11",180, 0, [500, 600, 700])
    assert np.array_equal(wvls1, wvls2)

    wvls3 = np.array([refl.get_reflectance("NG11",180, 0, w) for w in [500,600,700]], dtype=np.float32)
    assert np.array_equal(wvls1, wvls3)
