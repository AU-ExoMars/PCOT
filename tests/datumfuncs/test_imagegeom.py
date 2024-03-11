import numpy as np

from pcot import dq
from pcot.datum import Datum
from pcot.expressions import ExpressionEvaluator
from pcot.value import Value
import pcot.expressions.funcs as df

def test_flipv():
    # load a basic RGB image - no unc, no dq
    r = df.testimg(1)
    # create an uncertainty channel and add it
    unc = r*0.01
    r = df.v(r, unc)
    # test the top-right pixel just to make sure we created it right.
    pix = r.get(Datum.IMG)[255, 0]
    assert np.allclose([x.n for x in pix], [1, 0, 1])
    assert np.allclose([x.u for x in pix], [0.01, 0, 0.01])
    assert [x.dq for x in pix] == [0, 0, 0]
    # add DQ bits at the bottom left. Hack, and note the coordinate
    # reversal - the underlying arrays are [y,x] coordinate system
    r.get(Datum.IMG).dq[255, 0] = [dq.ERROR, dq.NONE, dq.SAT]
    pix = r.get(Datum.IMG)[0, 255]
    assert [x.dq for x in pix] == [dq.ERROR, dq.NONE, dq.SAT]

    r = df.flipv(r)
    img = r.get(Datum.IMG)
    assert img.channels == 3
    assert img.shape == (256, 256, 3)
    vals = [x.n for x in img[0, 0]]
    assert np.allclose(vals, [0, 1, 1])
    assert np.allclose([x.u for x in img[0, 0]], [0, 0.01, 0.01])
    assert [x.dq for x in img[0, 0]] == [dq.ERROR, dq.NONE, dq.SAT]


def test_fliph():
    # load a basic RGB image - no unc, no dq
    r = df.testimg(1)
    # create an uncertainty channel and add it
    unc = r*0.01
    r = df.v(r, unc)
    # add DQ bits at the top right. Hack, and note the coordinate
    # reversal - the underlying arrays are [y,x] coordinate system
    r.get(Datum.IMG).dq[0, 255] = [dq.ERROR, dq.NONE, dq.SAT]
    pix = r.get(Datum.IMG)[255, 0]
    assert [x.dq for x in pix] == [dq.ERROR, dq.NONE, dq.SAT]

    r = df.fliph(r)
    img = r.get(Datum.IMG)
    assert img.channels == 3
    assert img.shape == (256, 256, 3)
    vals = [x.n for x in img[0, 0]]
    assert np.allclose(vals, [1, 0, 1])
    assert np.allclose([x.u for x in img[0, 0]], [0.01, 0, 0.01])
    assert [x.dq for x in img[0, 0]] == [dq.ERROR, dq.NONE, dq.SAT]


def test_rotate():
    r = df.testimg(1)
    unc = r*0.01
    r = df.v(r, unc)
    r.get(Datum.IMG).dq[0, 0] = [dq.ERROR, dq.NONE, dq.SAT]

    # topright becomes top-left
    r = df.rotate(r, 90)
    pix = r.get(Datum.IMG)[0,0]
    assert np.allclose([x.n for x in pix], [1, 0, 1])
    assert np.allclose([x.u for x in pix], [0.01, 0, 0.01])
    assert [x.dq for x in pix] == [0, 0, 0]
    # test it this way too - we'll just do this from now on.
    assert r.get(Datum.IMG)[0, 0] == (
        Value(1, 0.01, dq.NONE),
        Value(0, 0, dq.NONE),
        Value(1, 0.01, dq.NONE)
    )

    # check that the bottom left is OK too
    assert r.get(Datum.IMG)[0, 255] == (
        Value(0, 0, dq.ERROR),
        Value(0, 0, dq.NONE),
        Value(0, 0, dq.SAT)
    )

    # now try again with 270 (one turn clockwise)
    r = df.testimg(1)
    unc = r*0.01
    r = df.v(r, unc)
    r.get(Datum.IMG).dq[0, 0] = [dq.ERROR|dq.TEST, dq.NONE, dq.SAT]
    r = df.rotate(r, 270)

    assert r.get(Datum.IMG)[0, 0] == (
        Value(0, 0, dq.NONE),
        Value(1, 0.01, dq.NONE),
        Value(1, 0.01, dq.NONE)
    )
    assert r.get(Datum.IMG)[255, 0] == (
        Value(0, 0, dq.ERROR|dq.TEST),
        Value(0, 0, dq.NONE),
        Value(0, 0, dq.SAT)
    )

    # and again to check that -90 is 270. (Slightly different vals, though)
    r = df.testimg(1)
    unc = r*0.02
    r = df.v(r, unc)
    r.get(Datum.IMG).dq[0, 0] = [dq.ERROR|dq.TEST, dq.NONE, dq.SAT|dq.DIVZERO]
    r = df.rotate(r, -90)
    assert r.get(Datum.IMG)[0, 0] == (
        Value(0, 0, dq.NONE),
        Value(1, 0.02, dq.NONE),
        Value(1, 0.02, dq.NONE)
    )
    assert r.get(Datum.IMG)[255, 0] == (
        Value(0, 0, dq.ERROR|dq.TEST),
        Value(0, 0, dq.NONE),
        Value(0, 0, dq.SAT|dq.DIVZERO)
    )




