"""Test functions that take an entire image and produce a scalar"""
from math import isclose

import pcot
from fixtures import gen_two_halves, genrgb
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document


def runop(doc, img, e, expectedn, expectedu):
    assert doc.setInputDirectImage(0, img) is None
    green = doc.graph.create("input 0", displayName="GREEN input")

    expr = doc.graph.create("expr")
    expr.expr = e
    expr.connect(0, green, 0, autoPerform=False)

    doc.changed()
    out = expr.getOutput(0, Datum.NUMBER)
    assert isclose(out.n, expectedn, abs_tol=1e-6)
    assert isclose(out.u, expectedu, abs_tol=1e-6)


def test_mean_const_3chan():
    # mean of a constant (0, 0.3, 0) image is 0.1. Why? Because "mean" doesn't work on
    # channels separately - it flattens the image first, so the resulting array is 0, 0.3, 0, 0, 0.3, 0...
    # The SD is going to be non-zero.
    pcot.setup()
    doc = Document()
    img = genrgb(50, 50, 0, 0.3, 0, doc=doc, inpidx=0)  # dark green
    runop(doc, img, "mean(a)", 0.1, 0.1414213627576828)


def test_mean_2halves():
    # mean of an image of two halves
    pcot.setup()
    doc = Document()
    img = gen_two_halves(50, 50, (0.1,), (0.0,), (0.2,), (0.0,), doc=doc, inpidx=0)
    runop(doc, img, "mean(a)", 0.15, 0.05)


def test_mean_2halves_diffuncs():
    # mean of an image of two halves with different uncertainties. This will be very diffent
    # because the uncertainties will be pooled.
    pcot.setup()
    doc = Document()
    img = gen_two_halves(50, 50, (0.1,), (1.0,), (0.2,), (2.0,), doc=doc, inpidx=0)
    runop(doc, img, "mean(a)", 0.15, 1.58192920)


def test_sd_const_grey():
    # SD of an image with all pixels the same grey colour (should be zero)
    pcot.setup()
    doc = Document()
    img = genrgb(50, 50, 0.1, 0.1, 0.1, doc=doc, inpidx=0)  # dark green
    runop(doc, img, "sd(a)", 0.0, 0.0)


def test_sd_const_nongrey():
    # SD of a tiny image with all pixels the same non-grey colour
    pcot.setup()
    doc = Document()
    img = genrgb(2, 2, 0, 1, 0, doc=doc, inpidx=0)  # dark green
    # result should be SD of (0,1,0, 0,1,0, 0,1,0, 0,1,0)
    runop(doc, img, "sd(a)", 0.4714045207910317, 0.0)


def test_sd_2halves():
    # SD of a tiny image of two colours
    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (0.0,), (2,), (0.0,), doc=doc, inpidx=0)
    runop(doc, img, "sd(a)", 0.5, 0.0)


def test_sd_2halves_diffuncs():
    # SD of a tiny image of two colours with two different SDs. The SDs of all the
    # pixels will be pooled, so the calculation will be
    # sqrt(variance([1,2,1,2]) + mean([4,5,4,5]**2)
    # pooled variance = variance of means + mean of variances.

    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (4.0,), (2,), (5.0,), doc=doc, inpidx=0)
    runop(doc, img, "sd(a)", 4.555217, 0.0)


def test_sd_2halves_diffuncs_bad():
    # Now make an SD of two colours the same way. Then set the two pixels
    # of the top half to be "BAD". These bad pixels should be ignored
    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (4.0,), (2,), (5.0,), doc=doc, inpidx=0)
    runop(doc, img, "mean(a)", 1.5, 4.555217)  # "smoke test" first
    img = gen_two_halves(2, 2, (1,), (4.0,), (2,), (5.0,), doc=doc, inpidx=0)
    img.dq[0] = (dq.NODATA, dq.NODATA)
    runop(doc, img, "mean(a)", 2.0, 5.0)  # bad pixels should be ignored, so we're just seeing the 2+-5 pixels.


def test_sum_nounc():
    # Sum of image of two colours. This is an addition, so we output the root of
    # the sum of the squares of the incoming SDs.
    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (0.0,), (2,), (0.0,), doc=doc, inpidx=0)
    runop(doc, img, "sum(a)", 6, 0.0)
    img = gen_two_halves(2, 2, (1,), (0.1,), (2,), (0.2,), doc=doc, inpidx=0)
    runop(doc, img, "sum(a)", 6, 0.31622776601683794)


def test_sum_unc():
    pcot.setup()
    doc = Document()
    img = gen_two_halves(2, 2, (1,), (0.1,), (2,), (0.2,), doc=doc, inpidx=0)
    runop(doc, img, "sum(a)", 6, 0.31622776601683794)
