from pcot.datum import Datum
from pcot.expressions import ExpressionEvaluator
import pcot.expressions.funcs as df
from fixtures import *
from pcot.xform import XFormException


def test_merge():
    # get the test image
    r = df.testimg(0)

    # extract the red, green and blue channels
    red = r % "R"
    green = r % "G"
    blue = r % "B"

    for img in [red, green, blue]:
        assert img.get(Datum.IMG).channels == 1
        assert img.get(Datum.IMG).shape == (256, 256)

    # merge them back together
    merged = df.merge(red, green, blue)

    # check that the merged image has three channels
    assert merged.get(Datum.IMG).channels == 3
    assert merged.get(Datum.IMG).shape == (256, 256, 3)

    # subtract this image from the original
    diff = r - merged
    # and check the resulting numbers are tiny
    n = diff.get(Datum.IMG).img
    assert np.abs(n).max() < 1e-10

    # put it back together differently for fun and make sure it's different
    merged = df.merge(blue, red, green)
    diff = r - merged
    n = diff.get(Datum.IMG).img
    assert np.abs(n).max() > 0.01


def test_grey_and_optional_args_py(rectimage):
    """This tests both the grey() function and a single optional argument from python."""
    r = df.testimg(0)
    g1 = df.grey(r)
    assert g1.get(Datum.IMG).channels == 1
    assert g1.get(Datum.IMG).shape == (256, 256)

    # do it the OpenCV way
    g2 = df.grey(r, 1)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() > 1e-10

    # do it the OpenCV way, providing the kwarg by name
    g2 = df.grey(r, opencv=1)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() > 1e-10

    # now with the opencv argument as zero.
    g2 = df.grey(r, 0)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() < 1e-10

    g2 = df.grey(r, opencv=0)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() < 1e-10


def test_grey_and_optional_args_expr():
    """This tests both the grey() function and a single optional argument from ExpressionEvaluator."""
    r = df.testimg(0)
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

    r = df.crop(d, 0, 0, 3, 3).get(Datum.IMG).img
    assert r.shape == (3, 3, 3)
    # top left corner is orange
    assert np.allclose(r[0, 0], [1, 0.6, 0.2])

    r = df.crop(d, 38, 28, 2, 2).get(Datum.IMG).img
    assert r.shape == (2, 2, 3)
    # bottom right is cyan
    assert np.allclose(r[0, 0], [0.3019608, 0.8, 0.6])

    # also works with coords too big
    r = df.crop(d, 38, 28, 20, 20).get(Datum.IMG).img
    assert r.shape == (2, 2, 3)
    # bottom right is cyan
    assert np.allclose(r[0, 0], [0.3019608, 0.8, 0.6])

    with pytest.raises(XFormException):
        r = df.crop(d, -3, -3, 6, 6).get(Datum.IMG).img

    with pytest.raises(XFormException):
        r = df.crop(d, 1, 1, 0, 0).get(Datum.IMG).img

    with pytest.raises(XFormException):
        r = df.crop(d, 1, 1, -2, -2).get(Datum.IMG).img


def test_rgb():
    # We'll just do this by converting a greyscale image to RGB; all the channels
    # should be the same.
    r = df.testimg(0)
    g = df.grey(r)
    assert g.get(Datum.IMG).channels == 1
    assert g.get(Datum.IMG).shape == (256, 256)

    # convert to RGB
    r = df.rgb(g)
    assert r.get(Datum.IMG).channels == 3
    assert r.get(Datum.IMG).shape == (256, 256, 3)

    # and check that all the channels are the same
    for i in range(3):
        assert np.allclose(r.get(Datum.IMG).img[:, :, i], g.get(Datum.IMG).img)


def test_v():
    r = df.testimg(0)
    assert np.all(r.get(Datum.IMG).dq == np.array([
        dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY],
        dtype=np.uint16))

    # apply an uncertainty to the image
    r = df.v(r, 0.1)  # numeric values are converted to Datum
    pix = r.get(Datum.IMG).img[0, 0]
    unc = r.get(Datum.IMG).uncertainty[0, 0]
    assert np.allclose(pix, [0.3882353, 0.21960784, 0.13725491])
    # and check that the uncertainty is set
    assert np.allclose(unc, [0.1, 0.1, 0.1])
    assert np.all(r.get(Datum.IMG).dq == np.array([0, 0, 0], dtype=np.uint16))

    # now apply an uncertainty which is 0.1 times the nominal of each pixel
    r = df.testimg(0)
    r = df.v(r, 0.1 * r)
    pix = r.get(Datum.IMG).img[0, 0]
    unc = r.get(Datum.IMG).uncertainty[0, 0]
    assert np.allclose(pix, [0.3882353, 0.21960784, 0.13725491])
    assert np.allclose(unc, [0.03882353, 0.021960784, 0.013725491])

    # now apply a fixed nominal to an uncertainty (a bit weird)
    r = df.testimg(0)
    r = df.v(0.1, r)
    pix = r.get(Datum.IMG).img[0, 0]
    unc = r.get(Datum.IMG).uncertainty[0, 0]
    assert np.allclose(unc, [0.3882353, 0.21960784, 0.13725491])
    # and check that the uncertainty is set
    assert np.allclose(pix, [0.1, 0.1, 0.1])
    assert np.all(r.get(Datum.IMG).dq == np.array([0, 0, 0], dtype=np.uint16))

    # finally generate a value
    r = df.v(0.1, 0.01)
    assert r.get(Datum.NUMBER).n == np.float32(0.1)
    assert r.get(Datum.NUMBER).u == np.float32(0.01)
    assert r.get(Datum.NUMBER).dq == dq.NONE

    # Here we are creating a value with an uncertainty of 0.0. There is still uncertainty
    # data, but it is 0.0. We don't want to treat this as a value with no uncertainty.
    r = df.v(0.1, 0.0)
    assert r.get(Datum.NUMBER).n == np.float32(0.1)
    assert r.get(Datum.NUMBER).u == np.float32(0.0)
    assert r.get(Datum.NUMBER).dq == dq.NONE

    # finally add some dq to an image, deleting all the uncertainty
    # (but not setting the uncertainty bit)
    r = df.testimg(0)
    r = df.v(r, dqbits=dq.ERROR)
    pix = r.get(Datum.IMG).img[0, 0]
    unc = r.get(Datum.IMG).uncertainty[0, 0]
    assert np.allclose(pix, [0.3882353, 0.21960784, 0.13725491])
    # and check that the uncertainty is set
    assert np.allclose(unc, [0, 0, 0])
    assert np.all(r.get(Datum.IMG).dq == np.array([dq.ERROR, dq.ERROR, dq.ERROR], dtype=np.uint16))


def test_nominal_and_uncertainty():
    r = df.testimg(0)
    n = df.nominal(r)
    u = df.uncertainty(r)
    assert np.allclose(n.get(Datum.IMG).img, r.get(Datum.IMG).img)
    assert np.allclose(u.get(Datum.IMG).img, r.get(Datum.IMG).uncertainty)

    # the resulting images should have no uncertainty
    assert np.allclose(n.get(Datum.IMG).uncertainty, 0)
    assert np.allclose(u.get(Datum.IMG).uncertainty, 0)

    # and should be marked in the dq bits as such

    assert np.all(n.get(Datum.IMG).dq == np.array([
        dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY],
        dtype=np.uint16))
    assert np.all(u.get(Datum.IMG).dq == np.array([
        dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY],
        dtype=np.uint16))
