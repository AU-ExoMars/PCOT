import numpy as np

from pcot.imagecube import ImageCube
from . import *


@pytest.fixture
def bwimage(globaldatadir):
    """Fixture to load a b/w image"""
    path = globaldatadir / 'basn0g01.png'
    return ImageCube.load(str(path), None, None)


@pytest.fixture
def rectimage(globaldatadir):
    """Fixture to load a rectangular test image"""
    path = globaldatadir / 'rect1.png'
    return ImageCube.load(str(path), None, None)


def test_load_image(bwimage):
    """Test that we can load an arbitrary BW image"""
    assert bwimage.channels == 3
    assert bwimage.h == 32
    assert bwimage.w == 32

    assert np.array_equal(bwimage.img[0][0], [1, 1, 1])
    assert np.array_equal(bwimage.img[bwimage.h - 1][bwimage.w - 1], [0, 0, 0])


def test_load_image2(rectimage):
    """A slightly tougher image; let's make sure the orientation is good"""
    assert rectimage.channels == 3
    assert rectimage.w == 40
    assert rectimage.h == 30

    assert np.allclose(rectimage.img[0][0], [1.0, 0.6, 0.2])
    assert np.allclose(rectimage.img[rectimage.h - 1][0], [1,1,1])
    assert np.allclose(rectimage.img[rectimage.h - 1][rectimage.w - 1], [30.2, 80, 60])
