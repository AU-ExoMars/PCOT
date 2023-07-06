"""Test binary and unary operators for uncertainty at the top (graph) level. Some
of these tests might seem redundant, because we also do them at the lower (Value) level.
But it's good to do some basic tests up here too.

There's a very handy calculator with uncertainties at https://uncertaintycalculator.com/

"""
from math import sqrt
from dataclasses import dataclass

import numpy as np
import pytest

import pcot
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document
from unc_fixtures import gen_2b_unc
import logging

logger = logging.getLogger(__name__)


def numberWithUncNode(doc, v, u):
    """Create a node which produces a number with an uncertainty value. Could do this with a single
    node and string manipulation on its expr, but this feels better somehow"""
    nodeV = doc.graph.create("constant")
    nodeU = doc.graph.create("constant")
    nodeV.val = v
    nodeU.val = u
    expr = doc.graph.create("expr")
    expr.expr = "v(a,b)"
    expr.connect(0, nodeV, 0, autoPerform=False)
    expr.connect(1, nodeU, 0, autoPerform=False)
    return expr


def test_make_unc():
    """Test that the scalar+uncertainty generator works"""
    pcot.setup()
    doc = Document()
    node = numberWithUncNode(doc, 1, 3)
    doc.changed()
    n = node.getOutput(0, Datum.NUMBER)
    assert n is not None
    assert n.n == 1
    assert n.u == 3


def test_number_unops():
    """Test that unary operations in expr nodes on numbers with uncertainty work. In the case of
    unary negation and inverse, (- and !) the uncertainty is passed through unchanged"""
    pcot.setup()

    def runop(a, ua, e, expected_val, expected_unc):
        """Inputs are:
            input nominal value
            input uncertainty
            expression ('a' is the input)
            expected output nominal
            expected output uncertainty"""
        doc = Document()
        node = numberWithUncNode(doc, a, ua)
        expr = doc.graph.create("expr")
        expr.expr = e
        expr.connect(0, node, 0, autoPerform=False)
        doc.changed()
        n = expr.getOutput(0, Datum.NUMBER)
        assert n is not None
        assert n.n == pytest.approx(expected_val)
        assert n.u == pytest.approx(expected_unc)

    runop(0, 0, "-a", 0, 0)
    runop(1, 0, "-a", -1, 0)
    runop(-1, 0, "-a", 1, 0)
    runop(1, 2, "-a", -1, 2)
    runop(-1, 2, "-a", 1, 2)
    # the ! operator actually maps to ~ or __invert__, which does 1-x.
    runop(0, 0, "!a", 1, 0)
    runop(1, 0, "!a", 0, 0)
    runop(1, 2, "!a", 0, 2)
    runop(0, 2, "!a", 1, 2)
    runop(-1, 2, "!a", 2, 2)  # "not -1" is a terrible thing to do, this is really an error.


@dataclass
class BinopTest:
    a: float  # Nominal value of A
    ua: float  # uncertainty of A
    b: float  # nominal value of B
    ub: float  # uncertainty of B
    e: str  # binary expression in A and B (e.g. "a+b")
    expected_val: float  # expected nominal result
    expected_unc: float  # expected uncertainty of result
    expected_dq: np.uint16  # expected DQ in result


# These are the tests - we repeat these for number/number, number/image, image/number and image/image
# Values are all generated using the uncertainties package or the uncertainty calculator
# at https://uncertaintycalculator.com/
tests = [
    BinopTest(10, 0, 20, 0, "a+b", 30, 0, dq.NONE),  # 10 + 20 = 30
    BinopTest(10, 2, 20, 5, "a+b", 30, sqrt(2 * 2 + 5 * 5), dq.NONE),  # 10±2 + 20±5 = 30±sqr(2^2+5^2)

    BinopTest(10, 0, 20, 0, "a-b", -10, 0, dq.NONE),  # 10 - 20 = 30
    BinopTest(10, 2, 20, 5, "a-b", -10, sqrt(2 * 2 + 5 * 5), dq.NONE),  # 10±2 + 20±5 = 30±sqr(2^2+5^2)

    BinopTest(10, 0, 20, 0, "a*b", 200, 0, dq.NONE),  # 10 * 20 = 200
    BinopTest(10, 2, 20, 3, "a*b", 200, 50.0, dq.NONE),  # 10±2 * 20±3 = 200±50
    BinopTest(20, 3, 10, 2, "a*b", 200, 50.0, dq.NONE),  # 20±3 * 20±2 = 200±50
    BinopTest(10, 3, 20, 2, "a*b", 200, 63.24555, dq.NONE),  # 10±3 * 20±2 = 200±63.24555 (approx)
    BinopTest(10, 3, -20, 2, "a*b", -200, 63.24555, dq.NONE),  # 10±3 * -20±2 = -200±63.24555 (approx)

    BinopTest(10, 0, 20, 0, "a/b", 0.5, 0, dq.NONE),
    BinopTest(10, 0, 20, 2, "a/b", 0.5, 0.05, dq.NONE),  # 10 / 20±2 = 200±0.05
    BinopTest(10, 2, 20, 0, "a/b", 0.5, 0.1, dq.NONE),  # 10±2 / 20 = 200±0.1
    BinopTest(10, 2, 20, 3, "a/b", 0.5, 0.125, dq.NONE),  # 10±2 / 20±3 = 200±0.125
    BinopTest(10, 3, 20, 2, "a/b", 0.5, 0.15811388, dq.NONE),  # 10±3 / 20±2 = 200±0.158 (approx)
    BinopTest(0, 0, 20, 2, "a/b", 0, 0, dq.NONE),  # 0 / 20±2 = 0
    BinopTest(0, 2, 20, 2, "a/b", 0, 0.1, dq.NONE),  # 0±2 / 20±2 = 0±0.1
    BinopTest(2, 0, 0, 0, "a/b", 0, 0, dq.DIVZERO),  # 2/0 = 0 but divzero flag set
    BinopTest(0, 0, 0, 0, "a/b", 0, 0, dq.DIVZERO | dq.UNDEF),  # 0/0 = 0 but divzero and undef set

    BinopTest(10, 2, 2, 3, "a^b", 100, 691.932677319881, dq.NONE),  # 10±2 ^ 2±3 = 100±691.932677319881
    BinopTest(3, 0.1, 2, 0.02, "a^b", 9, 0.631747691986546, dq.NONE),  # 3±0.1 ^ 2±0.02 = 9±0.631747691986546

    BinopTest(0, 2, 1, 3, "a^b", 0, 2, dq.NONE),  # 0±2 ^ 1±3 = 0±2 (i.e. 0^1 equals 0, with the uncertainty of the 0)
    BinopTest(0, 2, 0, 3, "a^b", 1, 0, dq.NONE),  # 0±2 ^ 0±3 = 1±0 (i.e. 0^0 = 1, uncertainties ignored)
    BinopTest(0, 2, -2, 3, "a^b", 0, 0, dq.UNDEF),  # 0±2 ^ -2±3 = 0±0 (actually UNDEF, can't raise zero to -ve power)
    BinopTest(0, 2, 0.2, 3, "a^b", 0, 0, dq.NONE),  # 0±2 ^ 0.2±3 = 0±0 (i.e. 0^n = 0 where n>0 and n!=1)
    BinopTest(0, 2, 4, 3, "a^b", 0, 0, dq.NONE),  # 0±2 ^ 4±3 = 0±0 (i.e. 0^n = 0 where n>0 and n!=1)

    BinopTest(1, 2, 4, 3, "a|b", 4, 3, dq.NONE),  # OR operator finds the maximum
    BinopTest(1, 2, 4, 3, "a&b", 1, 2, dq.NONE),  # AND operator finds the minimum

]


def test_number_number_ops():
    """Test that binary operations in expr nodes on numbers with uncertainty work."""
    pcot.setup()

    for t in tests:
        """(a,ua) and (b,ub) are scalar inputs with uncertainties. E is the expression."""
        doc = Document()
        nodeA = numberWithUncNode(doc, t.a, t.ua)
        nodeB = numberWithUncNode(doc, t.b, t.ub)
        expr = doc.graph.create("expr")
        expr.expr = t.e
        expr.connect(0, nodeA, 0, autoPerform=False)
        expr.connect(1, nodeB, 0, autoPerform=False)

        logger.warning(f"Testing {t.e} : a={t.a}±{t.ua}, b={t.b}±{t.ub} ----------------------------------------------")
        doc.changed()
        n = expr.getOutput(0, Datum.NUMBER)
        assert n is not None
        assert n.n == pytest.approx(t.expected_val)
        assert n.u == pytest.approx(t.expected_unc)
        assert n.dq == t.expected_dq


def check_binop_test(doc, t, expr, origimg):
    """Once the graph for a binop test is set up, we call this to check the answer.
    The area inside the ROI must have the expected value, unc, and dq. The area
    outside must be unchanged.

    The pixel at 8,8 in band 1 must also change despite being BAD.
    """

    logger.warning(f"Testing {t.e} : a={t.a}±{t.ua}, b={t.b}±{t.ub} ----------------------------------------------")

    doc.changed()
    img = expr.getOutput(0, Datum.IMG)  # has to be an image!
    assert img is not None

    expected_n = pytest.approx(t.expected_val)
    expected_u = pytest.approx(t.expected_unc)

    for x in range(0, 20):
        for y in range(0, 20):
            n = img.img[y, x, 1]
            u = img.uncertainty[y, x, 1]
            dqv = img.dq[y, x, 1]

            if 5 <= x < 15 and 5 <= y < 15:
                # check pixel is changed inside the rect
                en = expected_n
                eu = expected_u
                # and that the new DQ bit is OR-ed into the original - the 8,8 pixel is
                # has an existing bit set, so that should still be set.
                edq = t.expected_dq | origimg.dq[y, x, 1]
            else:
                # and unchanged outside
                en = origimg.img[y, x, 1]
                eu = origimg.uncertainty[y, x, 1]
                edq = origimg.dq[y, x, 1]

            ntest = n == en
            utest = u == eu
            dqtest = dqv == edq

            if not (ntest and utest and dqtest):
                logger.error(f"Error in binop test at pixel {x},{y} for expression {expr.expr}")
                if not ntest:
                    logger.error(f"N expected {en} got {n}")
                if not utest:
                    logger.error(f"U expected {eu} got {u}")
                if not dqtest:
                    logger.error(f"DQ expected {edq} got {dqv}")

            assert ntest and utest and dqtest


def test_number_image_ops():
    """Test than binops in expr nodes on numbers and images work, with the image on the RHS. We want to
    ensure that the part outside an ROI - and any "bad" parts of the image (with dq.BAD bits) - are unchanged."""

    pcot.setup()

    for t in tests:
        doc = Document()
        # node A just numeric.
        nodeA = numberWithUncNode(doc, t.a, t.ua)
        # node B is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        origimg = gen_2b_unc(2, 0.1, t.b, t.ub)

        # just to check that DQ bits get OR-ed in, we set some DQ in the image.
        origimg.dq[2, 2, 1] = dq.COMPLEX
        origimg.dq[8, 8, 1] = dq.SAT

        doc.setInputDirect(0, origimg)
        nodeB = doc.graph.create("input 0")
        # which feeds into a rect ROI
        rect = doc.graph.create("rect")
        rect.roi.set(5, 5, 10, 10)  # set the rectangle to be at 5,5 extending 10x10
        rect.connect(0, nodeB, 0, autoPerform=False)
        # and connect an expression node to nodeA and rect.
        expr = doc.graph.create("expr")
        expr.expr = t.e
        expr.connect(0, nodeA, 0, autoPerform=False)
        expr.connect(1, rect, 0, autoPerform=False)

        check_binop_test(doc, t, expr, origimg)


def test_image_number_ops():
    """Test than binops in expr nodes on images and numbers work, with the image on the LHS. We want to
    ensure that the part outside an ROI - and any "bad" parts of the image (with dq.BAD bits) - are unchanged.
    """

    pcot.setup()

    # I'm doing this deliberately without doing anything clever, as if I'd
    # never written the previous test (number/image)

    for t in tests:
        doc = Document()
        # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        origimg = gen_2b_unc(2, 0.1, t.a, t.ua)
        # just to check that DQ bits get OR-ed in, we set some DQ in the image.
        origimg.dq[2, 2, 1] = dq.COMPLEX
        origimg.dq[8, 8, 1] = dq.UNDEF
        doc.setInputDirect(0, origimg)
        nodeA = doc.graph.create("input 0")
        # which feeds into a rect ROI
        rect = doc.graph.create("rect")
        rect.roi.set(5, 5, 10, 10)  # set the rectangle to be at 5,5 extending 10x10
        rect.connect(0, nodeA, 0, autoPerform=False)

        # node B just numeric.
        nodeB = numberWithUncNode(doc, t.b, t.ub)
        # and connect an expression node to rect and nodeB.
        expr = doc.graph.create("expr")
        expr.expr = t.e
        # this is where the connections are reversed.
        expr.connect(0, rect, 0, autoPerform=False)
        expr.connect(1, nodeB, 0, autoPerform=False)

        check_binop_test(doc, t, expr, origimg)


def test_image_image_ops():
    """Test that binops work on image/image pairs, where the LHS image has an ROI on it."""

    pcot.setup()

    for t in tests:
        doc = Document()
        # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        imgA = gen_2b_unc(2, 0.1, t.a, t.ua)
        # just to check that DQ bits get OR-ed in, we set some DQ in the image.
        imgA.dq[2, 2, 1] = dq.COMPLEX
        imgA.dq[8, 8, 1] = dq.UNDEF
        doc.setInputDirect(0, imgA)
        nodeA = doc.graph.create("input 0")
        # which feeds into a rect ROI
        rect = doc.graph.create("rect")
        rect.roi.set(5, 5, 10, 10)  # set the rectangle to be at 5,5 extending 10x10
        rect.connect(0, nodeA, 0, autoPerform=False)

        # node B is a 20x20 2-band image with 3±0.2 in band 0 and the given values in band 1.
        imgB = gen_2b_unc(3, 0.2, t.b, t.ub)
        doc.setInputDirect(1, imgB)
        nodeB = doc.graph.create("input 1")
        # and connect an expression node to rect and nodeB.
        expr = doc.graph.create("expr")
        expr.expr = t.e
        # this is where the connections are reversed.
        expr.connect(0, rect, 0, autoPerform=False)
        expr.connect(1, nodeB, 0, autoPerform=False)

        check_binop_test(doc, t, expr, imgA)


def test_image_image_ops_noroi():
    """test image/image operations without a region of interest"""

    pcot.setup()

    for t in tests:
        doc = Document()
        # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        imgA = gen_2b_unc(2, 0.1, t.a, t.ua)
        # just to check that DQ bits get OR-ed in, we set some DQ in the image.
        imgA.dq[8, 8, 1] = dq.UNDEF
        doc.setInputDirect(0, imgA)
        nodeA = doc.graph.create("input 0")
        # node B is a 20x20 2-band image with 3±0.2 in band 0 and the given values in band 1.
        imgB = gen_2b_unc(3, 0.2, t.b, t.ub)
        doc.setInputDirect(1, imgB)
        nodeB = doc.graph.create("input 1")
        # and connect an expression node to rect and nodeB.
        expr = doc.graph.create("expr")
        expr.expr = t.e
        # this is where the connections are reversed.
        expr.connect(0, nodeA, 0, autoPerform=False)
        expr.connect(1, nodeB, 0, autoPerform=False)

        logger.warning(f"Testing {t.e} : a={t.a}±{t.ua}, b={t.b}±{t.ub} ----------------------------------------------")

        doc.changed()
        img = expr.getOutput(0, Datum.IMG)  # has to be an image!
        assert img is not None

        expected_n = pytest.approx(t.expected_val)
        expected_u = pytest.approx(t.expected_unc)

        for x in range(0, 20):
            for y in range(0, 20):
                n = img.img[y, x, 1]
                u = img.uncertainty[y, x, 1]
                dqv = img.dq[y, x, 1]

                ntest = n == expected_n
                utest = u == expected_u
                dqtest = dqv == t.expected_dq | imgA.dq[y, x, 1]

                if not (ntest and utest and dqtest):
                    logger.error(f"Error in binop test at pixel {x},{y} for expression {expr.expr}")
                    if not ntest:
                        logger.error(f"N expected {expected_n} got {n}")
                    if not utest:
                        logger.error(f"U expected {expected_u} got {u}")
                    if not dqtest:
                        logger.error(f"DQ expected {t.expected_dq | imgA.dq[y, x, 1]} got {dqv}")

                assert ntest and utest and dqtest
