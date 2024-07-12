"""Test operations - a lot of operations are covered already by things
in test_roi_principles, however, and also uncertainty/test_ops.py!"""
import math
from dataclasses import dataclass
from math import isclose

import pytest

import pcot
from fixtures import genrgb, gen_two_halves
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document
import numpy as np

from pcot.imagecube import ImageCube
from pcot.value import Value

tests = [
    ("12-10", 2),
    ("10", 10),
    ("4+10+16", 30),
    ("4*3+2", 14),
    ("2+4*3", 14),
    ("4*(3+2)", 20),
    ("(3+2)*4", 20),
    ("(3+2)/4", 1.25),
    ("(3+2)/4-10", -8.75),
    ("2^4", 16),
    ("4^0.5", 2),
    ("2&1", 1),
    ("2&20", 2),
    ("2|1", 2),
    ("2|20", 20)
]
testids = [f"{x[0]}=={x[1]}" for x in tests]


@pytest.mark.parametrize("e,expected", tests, ids=testids)
def test_scalar_ops(e, expected):
    """Basic scalar ops, testing precedence and brackets."""
    pcot.setup()
    doc = Document()
    expr = doc.graph.create("expr")
    expr.expr = e
    doc.run()
    n = expr.getOutput(0, Datum.NUMBER).n
    assert n == expected


tests = [
    # these are operations on an RGB image with pixels (0,0.5,0)
    ("a^(2+1)", (0, 0.125, 0)),
    ("a+4", (4, 4.5, 4)),
    ("4+a", (4, 4.5, 4)),
    ("a-0.5", (-0.5, 0, -0.5)),
    ("(a+2)/2", (1, 1.25, 1)),
    ("(a+2)/0", (0, 0, 0)),  # division by zero yields zero, but errors should be set. Tested elsewhere.
    ("a*2+1", (1, 2, 1)),
    ("a*(2+1)", (0, 1.5, 0))
]
testids = [f"{x[0]}=={x[1][0]},{x[1][1]},{x[1][2]}" for x in tests]


@pytest.mark.parametrize("e,expected", tests, ids=testids)
def test_image_scalar_ops(e, expected):
    """Smoke test for a basic image+scalar operation, no ROI"""
    pcot.setup()

    doc = Document()

    greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # dark green
    assert doc.setInputDirectImage(0, greenimg) is None
    green = doc.graph.create("input 0", displayName="GREEN input")

    expr = doc.graph.create("expr")
    expr.expr = e
    expr.connect(0, green, 0, autoPerform=False)

    doc.run()
    img = expr.getOutput(0, Datum.IMG)
    assert img is not None

    for x, y in ((0, 0), (49, 0), (49, 49), (0, 49)):
        assert np.array_equal(img.img[0, 0],
                              expected), f"{e}, got {img.img[0][0]} at {x},{y}. Expected {expected}, a=(0, 0.5, 0)"


# these are operations on an RGB image with pixels (0,0.5,0)
tests = [
    ("a+b", (2, 0.5, 0)),
    ("b+a", (2, 0.5, 0)),
    ("a-b", (-2, 0.5, 0)),
    ("a*b", (0, 0, 0))
]
testids = [f"{x[0]}=={x[1][0]},{x[1][1]},{x[1][2]}" for x in tests]


@pytest.mark.parametrize("e,expected", tests, ids=testids)
def test_image_image_ops(e, expected):
    """Very basic image ops"""
    pcot.setup()
    doc = Document()

    greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # dark green
    doc.setInputDirectImage(0, greenimg)
    redimg = genrgb(50, 50, 2, 0, 0, doc=doc, inpidx=1)  # oversaturated red
    doc.setInputDirectImage(1, redimg)
    green = doc.graph.create("input 0")
    red = doc.graph.create("input 1")

    expr = doc.graph.create("expr")
    expr.expr = e
    expr.connect(0, green, 0, autoPerform=False)
    expr.connect(1, red, 0, autoPerform=False)

    doc.run()
    img = expr.getOutput(0, Datum.IMG)
    assert img is not None

    for x, y in ((0, 0), (49, 0), (49, 49), (0, 49)):
        assert np.array_equal(img.img[0, 0], expected), f"{e}, got {img.img[0][0]} at {x},{y}"


@pytest.mark.filterwarnings("ignore:divide by zero")
@pytest.mark.filterwarnings("ignore:invalid value")
def test_scalar_div_zero():
    """Test scalar division by zero"""
    pcot.setup()
    doc = Document()
    expr = doc.graph.create("expr")
    expr.expr = "1/0"
    doc.run()
    d = expr.getOutputDatum(0)
    assert d.val == Value(0, 0, dq.DIVZERO)


def test_image_division_by_scalar_zero():
    """Test of dividing an image by scalar zero. Also checks that 0/0 comes out as undefined and divzero."""
    pcot.setup()
    doc = Document()
    greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # dark green
    assert doc.setInputDirectImage(0, greenimg) is None
    green = doc.graph.create("input 0")
    expr = doc.graph.create("expr")
    expr.expr = "a/0"
    expr.connect(0, green, 0)
    doc.run()
    d = expr.getOutput(0, Datum.IMG)
    assert d[0, 0] == (Value(0, 0, dq.DIVZERO | dq.NOUNCERTAINTY | dq.UNDEF),
                       Value(0, 0, dq.DIVZERO | dq.NOUNCERTAINTY),
                       Value(0, 0, dq.DIVZERO | dq.NOUNCERTAINTY | dq.UNDEF))


@pytest.mark.filterwarnings("ignore:divide by zero")
@pytest.mark.filterwarnings("ignore:invalid value")
def test_scalar_divide_by_zero_image():
    """Dividing by zero. We're trying to reciprocate an image where two of the bands are zero, which should
    lead to errors in those bands."""
    pcot.setup()
    doc = Document()
    greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # must have zeroes in it!
    assert doc.setInputDirectImage(0, greenimg) is None
    green = doc.graph.create("input 0")
    expr = doc.graph.create("expr")
    expr.expr = "1/a"
    expr.connect(0, green, 0)
    doc.run()
    d = expr.getOutput(0, Datum.IMG)

    assert d[0, 0] == (
        Value(0.0, 0.0, dq.NOUNCERTAINTY | dq.DIVZERO),
        Value(2.0, 0.0, dq.NOUNCERTAINTY),
        Value(0.0, 0.0, dq.NOUNCERTAINTY | dq.DIVZERO)
    )

    # now check 0/0

    expr.expr = "0/a"
    doc.run()
    d = expr.getOutput(0, Datum.IMG)

    assert d[0, 0] == (
        Value(0.0, 0.0, dq.NOUNCERTAINTY | dq.DIVZERO | dq.UNDEF),
        Value(0.0, 0.0, dq.NOUNCERTAINTY),
        Value(0.0, 0.0, dq.NOUNCERTAINTY | dq.DIVZERO | dq.UNDEF)
    )


def test_pixel_indexing_rgb():
    """Check that we can index into a multichannel ImageCube"""
    pcot.setup()
    doc = Document()
    inputimg = genrgb(50, 50,
                      4, 5, 6,  # rgb
                      u=(7, 8, 9),
                      doc=doc, inpidx=0)  # must have zeroes in it!
    inputimg.dq[0, 0, 0] = dq.SAT  # set 0,0 by hand

    assert doc.setInputDirectImage(0, inputimg) is None
    inpnode = doc.graph.create("input 0")
    doc.run()
    x = inpnode.getOutput(0, Datum.IMG)
    assert isinstance(x, ImageCube)
    p = x[0, 1]  # first check 0,1
    assert isinstance(p, tuple)
    assert len(p) == 3
    r, g, b = p

    # these equality tests are checked in basics/test_values
    assert r == Value(4, 7)
    assert g == Value(5, 8)
    assert b == Value(6, 9)

    # now check the 0,0 we changed the DQ with
    p = x[0, 0]
    assert p == (
        Value(4, 7, dq.SAT),
        Value(5, 8),
        Value(6, 9))
    assert p[0] != Value(4, 7)


def test_greyscale_simple():
    """Check that we can index into a 1-channel ImageCube."""
    pcot.setup()
    doc = Document()
    inputimg = genrgb(50, 50,
                      4, 5, 6,  # rgb
                      u=(7, 8, 9),
                      doc=doc, inpidx=0)  # must have zeroes in it!
    assert doc.setInputDirectImage(0, inputimg) is None
    inpnode = doc.graph.create("input 0")
    expr = doc.graph.create("expr")
    expr.expr = "grey(a)"
    expr.connect(0, inpnode, 0)
    doc.run()
    x = expr.getOutput(0, Datum.IMG)
    assert isinstance(x, ImageCube)
    p = x[0, 0]
    assert isinstance(p, Value)
    assert p.approxeq(Value(5, 8.082904))

    # and with an explicit false argument
    expr.expr = "grey(a,0)"
    doc.run()
    x = expr.getOutput(0, Datum.IMG)
    p = x[0, 0]
    assert p.approxeq(Value(5, 8.082904))


def test_greyscale_human():
    """now test that greyscaling with human perception of RGB works."""
    pcot.setup()
    doc = Document()
    inputimg = genrgb(50, 50,
                      4, 5, 6,  # rgb
                      u=(7, 8, 9),
                      doc=doc, inpidx=0)  # must have zeroes in it!
    assert doc.setInputDirectImage(0, inputimg) is None
    inpnode = doc.graph.create("input 0")
    expr = doc.graph.create("expr")
    expr.expr = "grey(a,1)"
    expr.connect(0, inpnode, 0)
    doc.run()
    x = expr.getOutput(0, Datum.IMG)
    p = x[0, 0]
    assert p.n == pytest.approx(4.815)
    assert p.u == 0
    assert p.dq == dq.NOUNCERTAINTY


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
        doc.setInputDirectImage(i, image)
        inputnode = doc.graph.create(f"input {i}")
        expr.connect(i, inputnode, 0)

    # change the expr to read each input in turn, run the graph each time and make sure the
    # output image is the right colour for that input
    for i, var in zip(range(4), ("a", "b", "c", "d")):
        expr.expr = var
        doc.run()
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

        doc.run()
        out = expr.getOutputDatum(0)
        assert out is Datum.null
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

        doc.run()
        out = expr.getOutputDatum(0)
        assert out is Datum.null
        assert expr.error.message == f"incompatible types for operator ADD: {ts}"


def test_null_image_input_binop():
    """Test that a null *image* input (Datum of type Image)
    into a binop produces an appropriate error"""

    pcot.setup()

    for s in ("a+4", "4+a", "a+b"):
        doc = Document()

        inpA = doc.graph.create("input 0")
        doc.setInputDirectImage(0, None)  # inputs created and set to None images.
        inpB = doc.graph.create("input 1")
        doc.setInputDirectImage(1, None)

        expr = doc.graph.create("expr")
        expr.expr = s
        expr.connect(0, inpA, 0)
        expr.connect(1, inpB, 0)

        doc.run()
        out = expr.getOutputDatum(0)
        assert out is Datum.null
        assert expr.error.message == "cannot perform binary operation on None image"
