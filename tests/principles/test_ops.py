"""Test operations - a lot of operations are covered already by things in test_roi_principles, however"""
import pytest

import pcot
from fixtures import genrgb
from pcot.datum import Datum
from pcot.document import Document
import numpy as np


def test_scalar_ops():
    def runop(e, expected):
        doc = Document()
        expr = doc.graph.create("expr")
        expr.expr = e
        doc.changed()
        n = expr.getOutput(0, Datum.NUMBER)
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
            assert np.array_equal(img.img[0, 0], expected), f"{e}, got {img.img[0][0]} at {x},{y}"

    runop("a+4", (4, 4.5, 4))
    runop("a-0.5", (-0.5, 0, -0.5))
    runop("(a+2)/2", (1, 1.25, 1))
    runop("a*2+1", (1, 2, 1))
    runop("a*(2+1)", (0, 1.5, 0))
    runop("4+a", (4, 4.5, 4))


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


def test_scalar_div_zero():
    """Test scalar division by zero"""
    pcot.setup()
    doc = Document()
    expr = doc.graph.create("expr")
    expr.expr = "1/0"
    doc.changed()
    d = expr.getOutputDatum(0)
    assert d is None
    assert expr.error.message == "float division by zero"


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
