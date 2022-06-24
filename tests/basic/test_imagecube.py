import numpy as np

import pcot
from pcot.document import Document
from pcot.filters import Filter
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.sources import InputSource, MultiBandSource
from . import *

pcot.setup()


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


def test_msimage(multispecimage):
    """Just check that we created this MS image OK, and that we have some kind of mapping in there."""
    assert multispecimage.channels == MS_NUMCHANS
    assert multispecimage.h == MS_HEIGHT
    assert multispecimage.w == MS_WIDTH
    assert type(multispecimage.mapping) == ChannelMapping

    # try to get an RGB image out
    rgb = multispecimage.rgb()