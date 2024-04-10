import numpy as np
import pytest

from fixtures import genrgb
from pcot.datum import Datum
from pcot.expressions.ops import OperatorException
from pcot.filters import Filter
from pcot.rois import ROIRect
from pcot.sources import Source, MultiBandSource, nullSourceSet


def test_band_extract_by_index():
    d = Datum(Datum.IMG, genrgb(32, 32, 3, 2, 1))
    r = d % "_0"  # extract the red band
    v = r.get(Datum.IMG)
    assert np.allclose(v.img[0, 0], 3)


def test_band_extract_by_wavelength():
    # now generate another image with wavelengths assigned to RGB

    img = genrgb(32, 32, 3, 2, 1)
    red = Source().setBand(Filter(640, 1.0, name="red"))
    green = Source().setBand(Filter(540, 1.0, name="green"))
    blue = Source().setBand(Filter(440, 1.0, name="blue"))
    img.sources = MultiBandSource([red, green, blue])

    # and test that the band extraction works with wavelengths

    r = Datum(Datum.IMG, img) % 540
    v = r.get(Datum.IMG)
    assert np.allclose(v.img[0, 0], 2)


def test_band_extract_by_name():
    img = genrgb(32, 32, 3, 2, 1)
    r = Datum(Datum.IMG, img) % "B"
    v = r.get(Datum.IMG)
    assert np.allclose(v.img[0, 0], 1)


def test_band_extract_single_band():
    # test that it works with a Datum that's just a single band
    d = Datum(Datum.IMG, genrgb(32, 32, 3, 2, 1))
    d = d % "_0"  # get first channel as a single band image
    d = d % "_0"  # and do that AGAIN.

    v = d.get(Datum.IMG)
    assert np.allclose(v.img[0, 0], 3)


def test_band_extract_badargs():
    with pytest.raises(OperatorException):
        Datum.k(10) % 10

    with pytest.raises(OperatorException):
        r = Datum(Datum.ROI, ROIRect(rect=(10, 10, 20, 20)), sources=nullSourceSet)
        r % 10

    with pytest.raises(OperatorException):
        d = Datum(Datum.IMG, genrgb(32, 32, 3, 2, 1))
        d % "X"
