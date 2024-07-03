"""Test functions that take an entire image and produce a scalar OR a vector"""
from math import isclose
from typing import Union

import numpy as np
import pytest

import pcot
from fixtures import gen_two_halves, genrgb
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document


def runop(doc, img, e, expectedn: Union[list, float], expectedu: Union[list, float], expecteddq=None):
    assert doc.setInputDirectImage(0, img) is None
    green = doc.graph.create("input 0", displayName="GREEN input")

    expr = doc.graph.create("expr")
    expr.expr = e
    expr.connect(0, green, 0, autoPerform=False)

    doc.run()
    out = expr.getOutput(0, Datum.NUMBER)

    if out.isscalar() and isinstance(expectedn, list):
        pytest.fail("Expected vector, got scalar")
    elif not out.isscalar() and not isinstance(expectedn, list):
        pytest.fail("Expected scalar, got vector")

    # the output can be vector or scalar, so we need to check and do the right test.
    if out.isscalar():
        try:
            # we have to use some tolerance here because we're working
            # with 32-bit floats
            assert np.allclose(out.n, expectedn, atol=1e-7)
            assert np.allclose(out.u, expectedu, atol=1e-7)
            if expecteddq is not None:
                assert out.dq == expecteddq
        except AssertionError:
            raise AssertionError(f"Expected N {expectedn}, got {out.n}. Expected U {expectedu}, got {out.u}")
    else:
        # convert the expected lists into arrays of the right type
        expns = np.array(expectedn, dtype=np.float32)
        expus = np.array(expectedu, dtype=np.float32)
        try:
            # see above for why we need to use a tolerance here
            assert np.allclose(out.n, expns, atol=1e-7)
            assert np.allclose(out.u, expus, atol=1e-7)
            if expecteddq is not None:
                assert np.array_equal(out.dq, expecteddq)
        except AssertionError:
            raise AssertionError(f"Expected N: {expns}, got {out.n}. Expected U: {expus}, got {out.u}")


def test_flatmean_const_3chan():
    # flatmean of a constant (0, 0.3, 0) image is 0.1. Why? Because "flatmean" doesn't work on
    # channels separately - it flattens the image first, so the resulting array is 0, 0.3, 0, 0, 0.3, 0...
    # The SD is going to be non-zero.
    pcot.setup()
    doc = Document()
    img = genrgb(50, 50, 0, 0.3, 0, doc=doc, inpidx=0)  # dark green
    runop(doc, img, "mean(flat(a))", 0.1, 0.1414213627576828)


def test_mean_const_3chan():
    # this will produce a vector of 3 means, one for each channel.

    pcot.setup()
    doc = Document()
    img = genrgb(50, 50, 0, 0.3, 0, doc=doc, inpidx=0)  # dark green
    runop(doc, img, "mean(flat(a))", 0.1, 0.1414213627576828)


def test_mean_2halves():
    # mean of an image of two halves
    pcot.setup()
    doc = Document()
    img = gen_two_halves(50, 50, (0.1,), (0.0,), (0.2,), (0.0,), doc=doc, inpidx=0)
    runop(doc, img, "mean(flat(a))", 0.15, 0.05)
    runop(doc, img, "mean(a)", 0.15, 0.05)


def test_mean_2halves_diffuncs():
    # mean of an image of two halves with different uncertainties. This will be very diffent
    # because the uncertainties will be pooled.

    pcot.setup()
    doc = Document()

    # this will generate an single-band image consisting of two halves:
    # 0.1+-0.01, 0.2+-0.02. We will get a mean of 0.15.

    # The variance of those means is 0.0025.
    # The variances are the squares of the standard deviations, so the variances are 0.0001 and 0.0004.
    # The mean of those is 0.00025.
    # The variance of the means, plus the mean of the variances, is 0.00275.
    # The root of that is 0.05244.

    img = gen_two_halves(50, 50, (0.1,), (0.01,), (0.2,), (0.02,), doc=doc, inpidx=0)
    runop(doc, img, "mean(a)", 0.15, 0.05244)


def test_mean_2halves_diffuncs_bad():
    # mean of an image of two halves with different uncertainties, but one of the halves is marked "bad"
    pcot.setup()
    doc = Document()

    img = gen_two_halves(2, 2, (0.1,), (0.01,), (0.2,), (0.02,), doc=doc, inpidx=0)
    img.dq[0] = (dq.NODATA, dq.NODATA)
    # the 0.1+-0.01 half is marked bad, so we should only see the 0.2+-0.02 half.
    runop(doc, img, "mean(a)", 0.2, 0.02)


def test_sd_const_grey():
    # SD of an image with all pixels the same grey colour (should be zero)
    pcot.setup()
    doc = Document()
    img = genrgb(50, 50, 0.1, 0.1, 0.1, doc=doc, inpidx=0)  # dark green
    runop(doc, img, "sd(a)", [0, 0, 0], [0, 0, 0])


def test_sd_const_nongrey():
    # SD of a tiny image with all pixels the same non-grey colour - again, should be zero.
    pcot.setup()
    doc = Document()
    img = genrgb(2, 2, 0, 1, 0, doc=doc, inpidx=0)  # dark green
    # result should be SD of (0,1,0, 0,1,0, 0,1,0, 0,1,0)
    runop(doc, img, "sd(a)", [0, 0, 0], [0, 0, 0])


def test_sd_2halves():
    # SD of a tiny image of two colours
    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (0.0,), (2,), (0.0,), doc=doc, inpidx=0)
    runop(doc, img, "sd(a)", 0.5, 0.0)


def test_sd_2halves_diffuncs():
    # SD of a tiny image of two colours with two different SDs.
    # pooled variance = variance of means + mean of variances.

    # Here, the numbers are 1+-4 and 2+-5 (a bit silly).
    # The variance of the means is 0.25.
    # The variances are 16 and 25. The mean of the variances is 20.5.
    # The pooled variance is 20.75. The root of that is 4.555217.

    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (4.0,), (2,), (5.0,), doc=doc, inpidx=0)
    runop(doc, img, "sd(a)", 4.555217, 0.0)


def test_sd_2halves_diffuncs_bad():
    # Now make an SD of two colours the same way. Then set the two pixels
    # of the top half to be "BAD". These bad pixels should be ignored
    pcot.setup()
    doc = Document()
    # img = gen_two_halves(2, 2, (1,), (4.0,), (2,), (5.0,), doc=doc, inpidx=0)
    # runop(doc, img, "mean(a)", 1.5, 4.555217)  # "smoke test" first

    img = gen_two_halves(2, 2, (1,), (4.0,), (2,), (5.0,), doc=doc, inpidx=0)
    img.dq[0] = (dq.NODATA, dq.NODATA)
    runop(doc, img, "mean(a)", 2.0, 5.0)  # bad pixels should be ignored, so we're just seeing the 2+-5 pixels.


def test_sum_nounc():
    # Sum of image of two colours. This is an addition, so we output the root of
    # the sum of the squares of the incoming SDs.
    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (0.0,), (2,), (0.0,), doc=doc, inpidx=0)
    runop(doc, img, "sum(a)", 6, 0.5)  # stddev of (1,1,2,2)=0.5


def test_sum_unc():
    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (0.1,), (2,), (0.2,), doc=doc, inpidx=0)
    runop(doc, img, "sum(a)", 6, 0.5916079878807068)


def test_max_2d():
    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (0.1,), (2,), (0.2,), doc=doc, inpidx=0)
    runop(doc, img, "max(a)", 2, 0.2, dq.NONE)


def test_min_3d():
    pcot.setup()
    doc = Document()
    img = genrgb(50, 50, 0, 0.3, 0, doc=doc, inpidx=0)  # dark green
    img.img[10, 10] = [-0.1, 0.2, 0.9]
    runop(doc, img, "min(a)", [-0.1, 0.2, 0], [0, 0, 0], [dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY])
