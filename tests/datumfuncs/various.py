from pcot.datum import Datum
from pcot.expressions import ExpressionEvaluator
from pcot.expressions.builtins import testimg, merge, grey, crop
from fixtures import *
from pcot.xform import XFormException


def test_merge():
    # get the test image
    r = testimg(0)

    # extract the red, green and blue channels
    red = r % "R"
    green = r % "G"
    blue = r % "B"

    for img in [red, green, blue]:
        assert img.get(Datum.IMG).channels == 1
        assert img.get(Datum.IMG).shape == (256, 256)

    # merge them back together
    merged = merge(red, green, blue)

    # check that the merged image has three channels
    assert merged.get(Datum.IMG).channels == 3
    assert merged.get(Datum.IMG).shape == (256, 256, 3)

    # subtract this image from the original
    diff = r - merged
    # and check the resulting numbers are tiny
    n = diff.get(Datum.IMG).img
    assert np.abs(n).max() < 1e-10

    # put it back together differently for fun and make sure it's different
    merged = merge(blue, red, green)
    diff = r - merged
    n = diff.get(Datum.IMG).img
    assert np.abs(n).max() > 0.01


def test_grey_and_optional_args_py(rectimage):
    """This tests both the grey() function and a single optional argument from python."""
    r = testimg(0)
    g1 = grey(r)
    assert g1.get(Datum.IMG).channels == 1
    assert g1.get(Datum.IMG).shape == (256, 256)

    # do it the OpenCV way
    g2 = grey(r, 1)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1-g2).get(Datum.IMG).img
    assert np.abs(img).max() > 1e-10

    # do it the OpenCV way, providing the kwarg by name
    g2 = grey(r, opencv=1)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1-g2).get(Datum.IMG).img
    assert np.abs(img).max() > 1e-10

    # now with the opencv argument as zero.
    g2 = grey(r, 0)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1-g2).get(Datum.IMG).img
    assert np.abs(img).max() < 1e-10

    g2 = grey(r, opencv=0)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1-g2).get(Datum.IMG).img
    assert np.abs(img).max() < 1e-10


def test_grey_and_optional_args_expr():
    """This tests both the grey() function and a single optional argument from ExpressionEvaluator."""
    r = testimg(0)
    e = ExpressionEvaluator()
    g1 = e.run("grey(a)", {'a': r})
    assert g1.get(Datum.IMG).channels == 1
    assert g1.get(Datum.IMG).shape == (256, 256)

    # do it the OpenCV way
    g2 = e.run("grey(a, 1)", {'a': r})
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() > 1e-10

    # NOTE - no keyword arguments in ExpressionEvaluator!

    # now with the opencv argument as zero.
    g2 = e.run("grey(a, 0)", {'a': r})
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() < 1e-10


def test_crop(rectimage):
    d = Datum(Datum.IMG, rectimage)

    r = crop(d, 0, 0, 3, 3).get(Datum.IMG).img
    assert r.shape == (3, 3, 3)
    # top left corner is orange
    assert np.allclose(r[0, 0], [1, 0.6, 0.2])

    r = crop(d, 38, 28, 2, 2).get(Datum.IMG).img
    assert r.shape == (2, 2, 3)
    # bottom right is cyan
    assert np.allclose(r[0, 0], [0.3019608, 0.8, 0.6])

    # also works with coords too big
    r = crop(d, 38, 28, 20, 20).get(Datum.IMG).img
    assert r.shape == (2, 2, 3)
    # bottom right is cyan
    assert np.allclose(r[0, 0], [0.3019608, 0.8, 0.6])

    with pytest.raises(XFormException):
        r = crop(d, -3, -3, 6, 6).get(Datum.IMG).img

    with pytest.raises(XFormException):
        r = crop(d, 1, 1, 0, 0).get(Datum.IMG).img

    with pytest.raises(XFormException):
        r = crop(d, 1, 1, -2, -2).get(Datum.IMG).img
