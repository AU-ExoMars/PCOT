import numpy as np

from pcot import dq
from pcot.datum import Datum
import pcot.datumfuncs as df
from pcot.value import Value


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


def test_trig_funcs():
    x = Datum.k(3.0, 0.1)
    assert df.sin(x).get(Datum.NUMBER).approxeq(Value(
        0.141120008059867,
        0.0989992496600445,
        dq.NONE))

    assert df.cos(x).get(Datum.NUMBER).approxeq(Value(
        -0.989992496600445,
        0.0141120008059867,
        dq.NONE))

    assert df.tan(x).get(Datum.NUMBER).approxeq(Value(
        -0.142546543074278,
        0.102031951694242,
        dq.NONE))

    v = df.tan(Datum.k(-np.pi/2, 0.1)).get(Datum.NUMBER)
    assert v.n > 1e6
    assert v.u > 1e6
    assert v.dq == dq.DIVZERO

    v = df.tan(Datum.k(np.pi/2, 0.1)).get(Datum.NUMBER)
    assert v.n < -1e6
    assert v.u > 1e6
    assert v.dq == dq.DIVZERO


def test_abs():
    assert df.abs(Datum.k(3, 0.1)).get(Datum.NUMBER).approxeq(Value(3, 0.1, dq.NONE))
    assert df.abs(Datum.k(-3, 0.1)).get(Datum.NUMBER).approxeq(Value(3, 0.1, dq.NONE))


def test_sqrt():
    assert df.sqrt(Datum.k(4, 0.1)).get(Datum.NUMBER).approxeq(Value(2, 0.025, dq.NONE))
    assert df.sqrt(Datum.k(2, 0.1)).get(Datum.NUMBER).approxeq(Value(1.4142135623730951, 0.0353553390593272, dq.NONE))
    assert df.sqrt(Datum.k(0, 0.1)).get(Datum.NUMBER).approxeq(Value(0, 0, dq.NONE))
    # it's weird that the uncertainty can be calculated and isn't complex while the nominal is complex, but it
    # does make sense.
    assert df.sqrt(Datum.k(-1, 0.1, dq.COMPLEX | dq.TEST)).get(Datum.NUMBER).approxeq(Value(0, 0.05, dq.COMPLEX | dq.TEST))
