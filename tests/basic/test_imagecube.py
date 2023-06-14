"""Tests on basic imagecube operations"""
import pcot
from pcot.document import Document
from pcot.filters import Filter
from pcot.sources import InputSource, MultiBandSource, SourceSet
import pcot.utils.image as image

from fixtures import *

pcot.setup()

# these are the shuffled channel indices from which we generate the multispec
# image parameters. We don't want them monotonic, basically.
MS_CHANS = (8, 5, 6, 3, 7, 4, 9, 1, 0, 2)
MS_NUMCHANS = len(MS_CHANS)
MS_WIDTH = 100
MS_HEIGHT = 50


@pytest.fixture
def multispecimage():
    """Fixture to generate a multispectral image with some fudged-up filter data"""
    # fake document
    doc = Document()
    # first let's fake some sources. I don't want the filter bands in linear order, though.
    sources = [InputSource(doc, inputIdx=1,
                           filterOrName=Filter(cwl=100 + MS_CHANS[i] * 100, fwhm=10 + i,
                                               transmission=20 + i * 5,
                                               position=f"pos{i}",
                                               name=f"name{i}")) for i in range(MS_NUMCHANS)]
    sources = MultiBandSource(sources)
    # and some image data, which is the channel index * 0.1 (if there are 10 channels).
    bands = np.stack([np.full((MS_HEIGHT, MS_WIDTH), i / MS_NUMCHANS) for i in range(MS_NUMCHANS)], axis=-1).astype(
        np.float32)
    assert bands.shape == (MS_HEIGHT, MS_WIDTH, MS_NUMCHANS)
    return ImageCube(bands, ChannelMapping(), sources, defaultMapping=None)


def test_load_image(bwimage):
    """Test that we can load a 32x32 solid white image from a PNG. It just does some very basic checks on
    the image pixels."""
    assert bwimage.channels == 3
    assert bwimage.h == 32
    assert bwimage.w == 32

    assert np.array_equal(bwimage.img[0][0], [1, 1, 1])
    assert np.array_equal(bwimage.img[bwimage.h - 1][bwimage.w - 1], [0, 0, 0])


def test_load_image2(rectimage):
    """A slightly tougher image - a white rect with colour blobs at the corners. Let's make sure the orientation
    is good, and that we are converting 8bit into 32bit float correctly. Again, it just loads an image from a PNG."""
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
    """Checks that we can split a colour RGB image and remerge it. Only tests the pixels, not uncertainty
    or DQ."""
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
    """Just check that we created this image OK, and that we have some kind of mapping in there."""
    assert multispecimage.channels == MS_NUMCHANS
    assert multispecimage.h == MS_HEIGHT
    assert multispecimage.w == MS_WIDTH
    assert type(multispecimage.mapping) == ChannelMapping

    # the image will have been made without a default mapping. We will guess the mapping
    # from the filter wavelengths. Since the cwls are (8, 5, 6, 3, 7, 4, 9, 1, 0, 2) * 100 + 100
    # (see MS_CHANS and how the filter sources are generated in the multispecimage fixture)
    # that gives (900,600,700,400,800,500,1000,200,100,300). The closest indices in that array
    # to 640,540,440 are 1,5,3.
    assert multispecimage.mapping.red == 1
    assert multispecimage.mapping.green == 5
    assert multispecimage.mapping.blue == 3

    # try to get an RGB image out which is the right shape and has the right values according to
    # the mapping we established above.
    rgb = multispecimage.rgb()
    assert type(rgb) == np.ndarray
    assert rgb.shape == (MS_HEIGHT, MS_WIDTH, 3)

    # make sure the RGB values are what they should be given the MS_CHANS array.
    r, g, b = image.imgsplit(rgb)
    assert np.isclose(np.max(r), 0.1)  # r = chan 1
    assert np.isclose(np.min(r), 0.1)
    assert np.isclose(np.max(g), 0.5)  # g = chan 5
    assert np.isclose(np.min(g), 0.5)
    assert np.isclose(np.max(b), 0.3)
    assert np.isclose(np.min(b), 0.3)


def makesource(doc, pos, cwl, fwhm):
    return InputSource(doc, inputIdx=-1, filterOrName=Filter(cwl, fwhm=fwhm, transmission=20 + pos * 5,
                                                             position=f"pos{pos}", name=f"name{pos}"))


def test_wavelength():
    """Create an image with some weird bands in it - bands with combined wavelengths - and check that
    wavelengthBand() works, correctly getting the single wavelength bands."""

    doc = Document()
    # note - NOT the same as in multispecimage.
    rootsources = [makesource(doc, i, cwl=100 + i * 100, fwhm=10 + i) for i in range(10)]

    sources = [
        rootsources[0],
        rootsources[1],
        SourceSet([rootsources[0], rootsources[2], rootsources[3]]),
        rootsources[2]
    ]
    count = len(sources)

    sources = MultiBandSource(sources)
    # and some image data, which is the channel index * 0.1 (if there are 10 channels).
    bands = np.stack([np.full((MS_HEIGHT, MS_WIDTH), i / count) for i in range(count)], axis=-1).astype(
        np.float32)
    img = ImageCube(bands, ChannelMapping(), sources, defaultMapping=None)

    assert img.wavelengthBand(100) == 0
    assert img.wavelengthBand(200) == 1
    assert img.wavelengthBand(300) == 3


def test_wavelength_widest():
    """Create an image with multiple RGB bands (among others) with the same CWL and make sure that
    wavelengthBand gets the widest one. This gets used in guessing RGB channels."""
    doc = Document()
    sources = [
        makesource(doc, 0, 640, 10),
        makesource(doc, 1, 640, 20),
        makesource(doc, 2, 640, 30),

        makesource(doc, 3, 540, 30),
        makesource(doc, 4, 540, 10),
        makesource(doc, 5, 540, 30),    # correct 540 candidate
        makesource(doc, 6, 300, 50),
        makesource(doc, 7, 550, 100),  # interesting case!

        makesource(doc, 8, 440, 10),
        makesource(doc, 9, 440, 20),
        makesource(doc, 10, 200, 10),
        makesource(doc, 11, 440, 30),   # correct 440 candidate
        makesource(doc, 12, 440, 20),
        makesource(doc, 13, 440, 8),
        makesource(doc, 14, 640, 100),    # correct 640 candidate
        makesource(doc, 15, 640, 5)
    ]
    count = len(sources)
    sources = MultiBandSource(sources)
    bands = np.stack([np.full((MS_HEIGHT, MS_WIDTH), i / count) for i in range(count)], axis=-1).astype(
        np.float32)
    img = ImageCube(bands, ChannelMapping(), sources, defaultMapping=None)

    assert img.wavelengthBand(640) == 14
