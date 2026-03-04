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
        return pcot.cameras.getReflectance("Colorchecker")
    except pcot.cameras.ReflectanceNotFoundException:
        pytest.xfail("Reflectance not found")

def test_simple_reflectance_bad_patch():
    # let's get some data for phi=0, theta=0
    refl = load()
    with pytest.raises(KeyError):
        # Check that unknown patches raise an error
        refl.get_reflectances("QUOP", 0, 0)

def test_simple_reflectance_single_val_extrapolate_theta():
    refl = load()
    inrange = refl.get_reflectance("purp",180, -80, 700)
    outofrange = refl.get_reflectance("purp", 180, -90, 700)
    # should be identical - theta is ignored
    assert outofrange == inrange

def test_simple_reflectance_single_val_extrapolate_w():
    # same goes for interpolating wavelengths out of range.
    refl = load()
    inrange = refl.get_reflectance("purp",180, 0, 700)
    outofrange = refl.get_reflectance("purp", 180, 0, 200)
    assert outofrange < inrange

def test_simple_reflectance_single_val_extrapolate_clamp():
    # check the out of range vals are clamped to zero
    refl = load()
    outofrange = refl.get_reflectance("purp", 180, 0, 200)
    assert outofrange == 0.0

def test_simple_reflectance_get_all():
    # check we can get all the wavelengths, that the result is a tuple of 1D arrays,
    # and that the arrays have the same shape.
    refl = load()
    wvls = refl.get_reflectances("purp",180, 0)
    assert len(wvls[0].shape)==1
    assert np.array_equal(wvls[0].shape,wvls[1].shape)

def test_simple_reflectance_get_subset_list():
    # try getting a subset of wavelengths as a list
    refl = load()
    wvls = refl.get_reflectances("purp",180, 0, [500, 600, 700, 800])
    assert len(wvls.shape)==1
    assert wvls.shape[0] == 4
    assert np.all(wvls < 0.9) # make sure the results look like valid reflectances!

def test_simple_reflectance_get_subset_nparray():
    # try getting a subset of wavelengths with nparray
    refl = load()
    r = refl.get_reflectances("purp",180, 0, np.array([500, 600, 700]))
    assert len(r.shape)==1
    assert r.shape[0] == 3
    assert np.all(r < 0.9) # make sure the results look like valid reflectances!

def test_simple_reflectance_get_subset_agree():
    # check that all three methods agree - getting using list, nparray, and individual vals
    refl = load()
    r1 = refl.get_reflectances("purp",180, 0, np.array([500, 600, 700]))
    r2 = refl.get_reflectances("purp",180, 0, [500, 600, 700])
    assert np.array_equal(r1, r2)

    r3 = np.array([refl.get_reflectance("purp",180, 0, w) for w in [500,600,700]], dtype=np.float64)
    assert np.array_equal(r1, r3)
