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
    """A slightly tougher image - a white rect with colour blobs at the corners. Let's make sure the orientation
    is good, and that we are converting 8bit into 32bit float correctly"""
    assert rectimage.channels == 3
    assert rectimage.w == 40
    assert rectimage.h == 30

    assert np.allclose(rectimage.img[0][0], [1.0, 0.6, 0.2])        # 100%, 60%, 20% = FF9933
    assert np.allclose(rectimage.img[rectimage.h - 1][0], [0.4, 0.8, 0.0])
    assert np.allclose(rectimage.img[0][rectimage.w - 1], [1, 1, 1])
    # note the atol here, that's to deal with the 0.302
    # Colour is : 30.2% (ish), 80%, 60% = 4DCC99
    assert np.allclose(rectimage.img[rectimage.h - 1][rectimage.w - 1], [0.302, 0.8, 0.6], atol=0.0001)
