import numpy as np

import pcot
from pcot.document import Document
from pcot.filters import Filter
from pcot.imagecube import ChannelMapping
from pcot.sources import InputSource, MultiBandSource
import pcot.utils.image as image

from fixtures import *

pcot.setup()


MS_NUMCHANS = 10
MS_WIDTH = 100
MS_HEIGHT = 50


@pytest.fixture
def multispecimage():
    """Fixture to generate a multispectral image with some fudged-up filter data"""
    # fake document
    doc = Document()
    # first let's fake some sources

    sources = [InputSource(doc, inputIdx=1,
                           filterOrName=Filter(cwl=1000 + i * 100, fwhm=10 + i, transmission=20 + i * 5,
                                               position=f"pos{i}",
                                               name=f"name{i}")) for i in range(MS_NUMCHANS)]
    sources = MultiBandSource(sources)
    # and some image data
    bands = np.stack([np.full((MS_HEIGHT, MS_WIDTH), i / MS_NUMCHANS) for i in range(MS_NUMCHANS)], axis=-1).astype(
        np.float32)
    assert bands.shape == (MS_HEIGHT, MS_WIDTH, MS_NUMCHANS)
    return ImageCube(bands, ChannelMapping(), sources, defaultMapping=None)


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

    assert np.allclose(rectimage.img[0][0], [1.0, 0.6, 0.2])  # 100%, 60%, 20% = FF9933
    assert np.allclose(rectimage.img[rectimage.h - 1][0], [0.4, 0.8, 0.0])
    assert np.allclose(rectimage.img[0][rectimage.w - 1], [1, 1, 1])
    # note the atol here, that's to deal with the 0.302
    # Colour is : 30.2% (ish), 80%, 60% = 4DCC99
    assert np.allclose(rectimage.img[rectimage.h - 1][rectimage.w - 1], [0.302, 0.8, 0.6], atol=0.0001)


def test_split_merge(rectimage):
    # make sure this does the same as cv.split
    img = image.imgsplit(rectimage.img)
    assert img[0].shape == (30, 40)
    assert img[1].shape == (30, 40)
    assert img[2].shape == (30, 40)
    # here we do the same tests as test_load_image2 but on each channel
    assert np.allclose(img[0][0][0], 1.0)
    assert np.allclose(img[1][0][0], 0.6)
    assert np.allclose(img[2][0][0], 0.2)
    assert np.allclose(img[0][rectimage.h - 1][0], 0.4)
    assert np.allclose(img[1][rectimage.h - 1][0], 0.8)
    assert np.allclose(img[2][rectimage.h - 1][0], 0.0)


def test_msimage(multispecimage):
    """Just check that we created this MS image OK, and that we have some kind of mapping in there."""
    assert multispecimage.channels == MS_NUMCHANS
    assert multispecimage.h == MS_HEIGHT
    assert multispecimage.w == MS_WIDTH
    assert type(multispecimage.mapping) == ChannelMapping

    # the image will have been made without a default mapping, so the mapping should be 0,1,2.
    assert multispecimage.mapping.red == 0
    assert multispecimage.mapping.green == 1
    assert multispecimage.mapping.blue == 2

    # try to get an RGB image out which is the right shape and has the right values according to
    # the mapping we established above.
    rgb = multispecimage.rgb()
    assert type(rgb) == np.ndarray
    assert rgb.shape == (MS_HEIGHT, MS_WIDTH, 3)

    # make sure the RGB values are what they should be: channelnumber / MS_NUMCHANS
    r, g, b = image.imgsplit(rgb)
    assert np.max(r) == np.min(r) == 0
    assert np.isclose(np.max(g), 0.1)
    assert np.isclose(np.min(g), 0.1)
    assert np.isclose(np.max(b), 0.2)
    assert np.isclose(np.min(b), 0.2)
