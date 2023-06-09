"""Test operations - a lot of operations are covered already by things in test_roi_principles, however"""
import math
from math import isclose

import pytest

import pcot
from fixtures import genrgb, gen_two_halves
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document
import numpy as np

from pcot.value import OpData


def test_scalar_ops():
    def runop(e, expected):
        doc = Document()
        expr = doc.graph.create("expr")
        expr.expr = e
        doc.changed()
        n = expr.getOutput(0, Datum.NUMBER).n
        assert n == expected

    pcot.setup()

    runop("12-10", 2)
    runop("10", 10)
    runop("4+10+16", 30)
    runop("4*3+2", 14)
    runop("2+4*3", 14)
    runop("4*(3+2)", 20)
    runop("(3+2)*4", 20)
    runop("(3+2)/4", 1.25)
    runop("(3+2)/4-10", -8.75)
    runop("2^4", 16)
    runop("4^0.5", 2)
    runop("2&1", 1)
    runop("2&20", 2)
    runop("2|1", 2)
    runop("2|20", 20)


def test_image_scalar_ops():
    """Smoke test for a basic image+scalar operation, no ROI"""
    pcot.setup()

    def runop(e, expected):
        doc = Document()

        greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # dark green
        assert doc.setInputDirect(0, greenimg) is None
        green = doc.graph.create("input 0", displayName="GREEN input")

        expr = doc.graph.create("expr")
        expr.expr = e
        expr.connect(0, green, 0)

        doc.changed()
        img = expr.getOutput(0, Datum.IMG)
        assert img is not None

        for x, y in ((0, 0), (49, 0), (49, 49), (0, 49)):
            assert np.array_equal(img.img[0, 0], expected), f"{e}, got {img.img[0][0]} at {x},{y}. Expected {expected}, a=(0, 0.5, 0)"

    runop("a^(2+1)", (0, 0.125, 0))
    runop("a+4", (4, 4.5, 4))
    runop("4+a", (4, 4.5, 4))
    runop("a-0.5", (-0.5, 0, -0.5))
    runop("(a+2)/2", (1, 1.25, 1))
    runop("(a+2)/0", (0,0,0))       # division by zero yields zero, but errors should be set. Tested elsewhere.
    runop("a*2+1", (1, 2, 1))
    runop("a*(2+1)", (0, 1.5, 0))


def test_image_image_ops():
    pcot.setup()

    def runop(e, expected):
        doc = Document()

        greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # dark green
        doc.setInputDirect(0, greenimg)
        redimg = genrgb(50, 50, 2, 0, 0, doc=doc, inpidx=1)  # oversaturated red
        doc.setInputDirect(1, redimg)
        green = doc.graph.create("input 0")
        red = doc.graph.create("input 1")

        expr = doc.graph.create("expr")
        expr.expr = e
        expr.connect(0, green, 0)
        expr.connect(1, red, 0)

        doc.changed()
        img = expr.getOutput(0, Datum.IMG)
        assert img is not None

        for x, y in ((0, 0), (49, 0), (49, 49), (0, 49)):
            assert np.array_equal(img.img[0, 0], expected), f"{e}, got {img.img[0][0]} at {x},{y}"

    runop("a+b", (2, 0.5, 0))
    runop("b+a", (2, 0.5, 0))
    runop("a-b", (-2, 0.5, 0))
    runop("a*b", (0, 0, 0))

def test_image_stats():
    """Test functions that take an entire image and produce a scalar"""

    pcot.setup()
    doc = Document()
    def runop(img, e, expectedn, expectedu):
        assert doc.setInputDirect(0, img) is None
        green = doc.graph.create("input 0", displayName="GREEN input")

        expr = doc.graph.create("expr")
        expr.expr = e
        expr.connect(0, green, 0)

        doc.changed()
        out = expr.getOutput(0, Datum.NUMBER)
        assert isclose(out.n, expectedn, abs_tol=1e-6)
        assert isclose(out.u, expectedu, abs_tol=1e-6)


    # Currently the stats functions don't take account of any uncertainty in the pixels
    # mean of a constant (0, 0.3, 0) image is 0.1. Why? Because "mean" doesn't work on
    # channels separately - it flattens the image first, so the resulting array is 0, 0.3, 0, 0, 0.3, 0...
    # The SD is going to be non-zero.
    img = genrgb(50, 50, 0, 0.3, 0, doc=doc, inpidx=0)  # dark green
    runop(img, "mean(a)", 0.1, 0.1414213627576828)

    # mean of an image of two halves
    img = gen_two_halves(50, 50, (0.1,), (0.0,), (0.2,), (0.0,), doc=doc, inpidx=0)
    runop(img, "mean(a)", 0.15, 0.05)

    # mean of an image of two halves with different uncertainties. It will be the same as the above,
    # but we're going to get a result with same the uncertainty because that's probably (a) too hard
    # (although we could use standard error of the mean) and (b) possibly meaningless?

    img = gen_two_halves(50, 50, (0.1,), (1.0,), (0.2,), (2.0,), doc=doc, inpidx=0)
    runop(img, "mean(a)", 0.15, 0.05)

    # SD of an image with all pixels the same grey colour (should be zero)
    img = genrgb(50, 50, 0.1, 0.1, 0.1, doc=doc, inpidx=0)  # dark green
    runop(img, "sd(a)", 0.0, 0.0)

    # SD of a tiny image with all pixels the same non-grey colour
    img = genrgb(2, 2, 0, 1, 0, doc=doc, inpidx=0)  # dark green
    # result should be SD of (0,1,0, 0,1,0, 0,1,0, 0,1,0)
    runop(img, "sd(a)", 0.4714045207910317, 0.0)

    # SD of a tiny image of two colours
    img = gen_two_halves(2, 2, (1,), (0.0,), (2,), (0.0,), doc=doc, inpidx=0)
    runop(img, "sd(a)", 0.5, 0.0)

    # SD of a tiny image of two colours with two different SDs. SDs are just ignored when
    # we combine them like this. This is almost certainly incorrect.
    img = gen_two_halves(2, 2, (1,), (4.0,), (2,), (5.0,), doc=doc, inpidx=0)
    runop(img, "sd(a)", 0.5, 0.0)

    # Now make an SD of two colours the same way. Then set the two pixels
    # of the top half to be "BAD".
    img = gen_two_halves(2, 2, (1,), (4.0,), (2,), (5.0,), doc=doc, inpidx=0)
    runop(img, "mean(a)", 1.5, 0.5)  # "smoke test" first
    img = gen_two_halves(2, 2, (1,), (4.0,), (2,), (5.0,), doc=doc, inpidx=0)
    img.dq[0] = (dq.NODATA, dq.NODATA)
    runop(img, "mean(a)", 2.0, 0.0)

    # Sum of image of two colours. This is an addition, so we output the root of
    # the sum of the squares of the incoming SDs.
    img = gen_two_halves(2, 2, (1,), (0.0,), (2,), (0.0,), doc=doc, inpidx=0)
    runop(img, "sum(a)", 6, 0.0)
    img = gen_two_halves(2, 2, (1,), (0.1,), (2,), (0.2,), doc=doc, inpidx=0)
    runop(img, "sum(a)", 6, 0.31622776601683794)


def test_scalar_div_zero():
    """Test scalar division by zero"""
    pcot.setup()
    doc = Document()
    expr = doc.graph.create("expr")
    expr.expr = "1/0"
    doc.changed()
    d = expr.getOutputDatum(0)
    assert d.val == OpData(0, 0, dq.DIVZERO)


def test_image_division_by_zero():
    """This test fails because dividing a masked array by zero produces another masked array
    in which the divzero members are masked out!

    What it should do is produce a result, but all the pixels should have an error bit set.
    """
    pcot.setup()
    doc = Document()
    greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # dark green
    assert doc.setInputDirect(0, greenimg) is None
    green = doc.graph.create("input 0")
    expr = doc.graph.create("expr")
    expr.expr = "a/0"
    expr.connect(0, green, 0)
    doc.changed()
    d = expr.getOutputDatum(0)

    pytest.fail("Error pixels not implemented")

    assert d is None
    assert expr.error.message == "float division by zero"


def test_scalar_divide_by_zero_image():
    """Should also produce an error"""
    pcot.setup()
    doc = Document()
    greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # must have zeroes in it!
    assert doc.setInputDirect(0, greenimg) is None
    green = doc.graph.create("input 0")
    expr = doc.graph.create("expr")
    expr.expr = "1/a"
    expr.connect(0, green, 0)
    doc.changed()
    d = expr.getOutputDatum(0)

    pytest.fail("Error pixels not implemented")

    assert d is None
    assert expr.error.message == "float division by zero"


def test_all_expr_inputs():
    """Make sure all expr inputs work."""

    pcot.setup()
    doc = Document()

    inputs = ("a", "b", "c", "d")
    cols = ((0, 0.5, 0), (1, 0.0, 0), (0, 0.5, 1), (1, 0.5, 1))

    expr = doc.graph.create("expr")

    # create four images, four input nodes, connect them to the expr node inputs A-D.
    for i, (r, g, b) in enumerate(cols):
        image = genrgb(50, 50, r, g, b, doc=doc, inpidx=i)
        doc.setInputDirect(i, image)
        inputnode = doc.graph.create(f"input {i}")
        expr.connect(i, inputnode, 0)

    # change the expr to read each input in turn, run the graph each time and make sure the
    # output image is the right colour for that input
    for i, var in zip(range(4), ("a", "b", "c", "d")):
        expr.expr = var
        doc.changed()
        img = expr.getOutput(0, Datum.IMG)
        assert img is not None
        assert np.array_equal(img.img[0, 0], cols[i]), f"Image input {var} failed"


def test_unconnected_input_binop():
    """Test that a null input (Datum of type NONE) into a binop produces an appropriate error. The error will actually
    be thrown before the binop even runs."""
    pcot.setup()

    for s in ("a+4", "4+a", "a+b"):
        doc = Document()

        expr = doc.graph.create("expr")  # unconnected input
        expr.expr = s

        doc.changed()
        out = expr.getOutputDatum(0)
        assert out is None
        assert expr.error.message == "variable's input is not connected"


def test_null_datum_input_binop():
    """Test that a null input (Datum of type None)
    into a binop produces an appropriate error"""

    pcot.setup()

    for s, ts in (("a+4", "none, number"), ("4+a", "number, none"), ("a+b", "none, none")):
        doc = Document()

        inpA = doc.graph.create("input 0")
        inpB = doc.graph.create("input 1")  # inputs created but not set; they'll be None (but not images)

        expr = doc.graph.create("expr")
        expr.expr = s
        expr.connect(0, inpA, 0)
        expr.connect(1, inpB, 0)

        doc.changed()
        out = expr.getOutputDatum(0)
        assert out is None
        assert expr.error.message == f"incompatible types for operator ADD: {ts}"


def test_null_image_input_binop():
    """Test that a null *image* input (Datum of type Image)
    into a binop produces an appropriate error"""

    pcot.setup()

    for s in ("a+4", "4+a", "a+b"):
        doc = Document()

        inpA = doc.graph.create("input 0")
        doc.setInputDirect(0, None)  # inputs created and set to None images.
        inpB = doc.graph.create("input 1")
        doc.setInputDirect(1, None)

        expr = doc.graph.create("expr")
        expr.expr = s
        expr.connect(0, inpA, 0)
        expr.connect(1, inpB, 0)

        doc.changed()
        out = expr.getOutputDatum(0)
        assert out is None
        assert expr.error.message == "cannot perform binary operation on None image"
