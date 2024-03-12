import numpy as np

from pcot import dq
from pcot.datum import Datum
import pcot.expressions.funcs as df
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

