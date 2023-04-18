"""Test the creation of image with uncertainty and DQ bits"""
import numpy as np
import pytest

from fixtures import genrgb
from pcot.dq import NOUNCERTAINTY
from pcot.imagecube import ImageCube
from unc_fixtures import gen_2b_unc


def test_create_unmatched_unc_shape():
    data = np.full((20, 20), 0, np.float32)
    uncd = np.full((20, 21), 0, np.float32)
    with pytest.raises(Exception) as info:
        img = ImageCube(data, uncertainty=uncd)
    assert "uncertainty data is not same shape as image data" == str(info.value)


def test_create_wrong_unc_type():
    """Test that an incorrect type passed as uncertainty is converted."""
    data = np.full((20, 20), 0, np.float32)
    uncd = np.full((20, 20), 0.5, np.float)
    with pytest.raises(Exception) as info:
        img = ImageCube(data, uncertainty=uncd)
    assert "uncertainty data must be 32-bit floating point" == str(info.value)


def test_create_unmatched_dq_shape():
    data = np.full((20, 20), 0, np.float32)
    dqd = np.full((20, 21), 0, np.uint16)
    with pytest.raises(Exception) as info:
        img = ImageCube(data, dq=dqd)
    assert "DQ data is not same shape as image data" == str(info.value)


def test_create_wrong_dq_type():
    """Test that an incorrect type passed as uncertainty is converted."""
    data = np.full((20, 20), 0, np.float32)
    dqd = np.full((20, 20), 0.5, np.float)
    with pytest.raises(Exception) as info:
        img = ImageCube(data, dq=dqd)
    assert "DQ data is not 16-bit unsigned integers" == str(info.value)


def test_create_unc_2b_ok():
    """Basic test of creating a 2-band image with uncertainty"""
    img = gen_2b_unc(1, 2, 3, 4)
    u = img.uncertainty[10, 10]
    d = img.img[10, 10]
    assert np.array_equal(u, np.array((3, 4), np.float32))
    assert np.array_equal(d, np.array((1, 2), np.float32))


def test_default_dq():
    """Test that creating an image with uncertainty creates zero DQ (assuming no other problems)"""
    img = gen_2b_unc(1, 2, 3, 4)
    assert np.array_equal(np.zeros(img.shape, dtype=np.uint16), img.dq)


def test_nounc_dq():
    """Test that creating an image with no uncertainty data creates NOUNC dq bits"""
    img = genrgb(20, 20, 0, 0, 0)  # black RGB image, 20x20
    assert np.array_equal(np.full(img.shape, NOUNCERTAINTY, dtype=np.uint16), img.dq)
