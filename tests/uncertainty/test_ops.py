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


def numberWithUncNode(doc, v, u, dqv=0):
    """Create a node which produces a number with an uncertainty value. Could do this with a single
    node and string manipulation on its expr, but this feels better somehow"""
    nodeV = doc.graph.create("constant")
    nodeU = doc.graph.create("constant")
    nodeV.val = v
    nodeU.val = u
    expr = doc.graph.create("expr")
    expr.expr = f"v(a,b,{dqv})"
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


def check_op_test(doc, t, expr, origimg):
    """Once the graph for a test is set up, we call this to check the answer.
    The area inside the ROI must have the expected value, unc, and dq. The area
    outside must be unchanged. We can't check DQ propagation from binops, because
    different binops do it differently (e.g. max, min). There's another test for that.
    """

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
                # can't test that DQs are merged from parents; different ops do different things.
                # But we can at least do this for unary ops - we set the DQ on a couple of pixels
                # in the incoming image. We can do it for binops too if they aren't min,max.
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


######################################### Unary operation tests


@dataclass
class UnopTest:
    """An object defining the input, expression and output of a unary operation test"""
    n: float  # nominal value of argument
    u: float  # uncertainty of argument
    dq: np.uint16  # DQ of argument
    e: str  # unary expression in A  (e.g. "-a")
    expected_val: float  # expected nominal result
    expected_unc: float  # expected uncertainty of result
    expected_dq: np.uint16  # expected DQ in result


unop_tests = [

    UnopTest(0, 0, dq.NONE, "-a", 0, 0, dq.NONE),
    UnopTest(1, 0, dq.NONE, "-a", -1, 0, dq.NONE),
    UnopTest(-1, 0, dq.NONE, "-a", 1, 0, dq.NONE),
    UnopTest(1, 2, dq.NONE, "-a", -1, 2, dq.NONE),
    UnopTest(-1, 2, dq.NONE, "-a", 1, 2, dq.NONE),
    UnopTest(-1, 0, dq.SAT | dq.COMPLEX, "-a", 1, 0, dq.SAT | dq.COMPLEX),  # DQ must get passed through
    # the ! operator actually maps to ~ or __invert__, which does 1-x.
    UnopTest(0, 0, dq.NONE, "!a", 1, 0, dq.NONE),
    UnopTest(1, 0, dq.NONE, "!a", 0, 0, dq.NONE),
    UnopTest(1, 2, dq.NONE, "!a", 0, 2, dq.NONE),
    UnopTest(0, 2, dq.NONE, "!a", 1, 2, dq.NONE),
    UnopTest(-1, 2, dq.NONE, "!a", 2, 2, dq.NONE),  # "not -1" is an inappropriate thing to do, but we don't flag it

    # ensure pass-through of DQ
]


def test_number_unops():
    """Test that unary operations in expr nodes on numbers with uncertainty work. In the case of
    unary negation and inverse, (- and !) the uncertainty is passed through unchanged"""
    pcot.setup()

    for t in unop_tests:
        logger.warning(f"Testing {t.e} : a={t.n}±{t.u} dq={t.dq}----------------------------------------------")
        doc = Document()
        node = numberWithUncNode(doc, t.n, t.u, t.dq)
        expr = doc.graph.create("expr")
        expr.expr = t.e
        expr.connect(0, node, 0, autoPerform=False)
        doc.changed()
        n = expr.getOutput(0, Datum.NUMBER)
        assert n is not None
        assert n.n == pytest.approx(t.expected_val)
        assert n.u == pytest.approx(t.expected_unc)
        assert n.dq == t.expected_dq


def test_image_unops():
    """Test that unary operations in expr nodes on images with uncertainty work. Also ensure that
    the operation only acts on areas covered by an ROI and that DQs are passed through."""

    pcot.setup()
    for t in unop_tests:
        doc = Document()
        # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        img = gen_2b_unc(2, 0.1, t.n, t.u, dq0=0, dq1=t.dq)
        # just to check that DQ bits get OR-ed in (or rather passed through), we set some (more) DQ in the image.
        img.dq[2, 2, 1] |= dq.COMPLEX
        img.dq[8, 8, 1] |= dq.UNDEF
        doc.setInputDirect(0, img)
        nodeA = doc.graph.create("input 0")
        # which feeds into a rect ROI
        rect = doc.graph.create("rect")
        rect.roi.set(5, 5, 10, 10)  # set the rectangle to be at 5,5 extending 10x10
        rect.connect(0, nodeA, 0, autoPerform=False)
        # and connect an expression node to the rect.
        expr = doc.graph.create("expr")
        expr.expr = t.e
        # this is where the connections are reversed.
        expr.connect(0, rect, 0, autoPerform=False)

        # now run the test
        logger.warning(f"Testing {t.e} : a={t.n}±{t.u} dq={t.dq}----------------------------------------------")
        check_op_test(doc, t, expr, img)


######################################### Binary operation tests


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
binop_tests = [
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


def test_number_number_binops():
    """Test that binary operations in expr nodes on numbers with uncertainty work."""
    pcot.setup()

    for t in binop_tests:
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


def test_number_image_binops():
    """Test than binops in expr nodes on numbers and images work, with the image on the RHS. We want to
    ensure that the part outside an ROI - and any "bad" parts of the image (with dq.BAD bits) - are unchanged."""

    pcot.setup()

    for t in binop_tests:
        doc = Document()
        # node A just numeric.
        nodeA = numberWithUncNode(doc, t.a, t.ua)
        # node B is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        origimg = gen_2b_unc(2, 0.1, t.b, t.ub)

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

        logger.warning(f"Testing {t.e} : a={t.a}±{t.ua}, b={t.b}±{t.ub} ----------------------------------------------")
        check_op_test(doc, t, expr, origimg)


def test_image_number_binops():
    """Test than binops in expr nodes on images and numbers work, with the image on the LHS. We want to
    ensure that the part outside an ROI - and any "bad" parts of the image (with dq.BAD bits) - are unchanged.
    """

    pcot.setup()

    # I'm doing this deliberately without doing anything clever, as if I'd
    # never written the previous test (number/image)

    for t in binop_tests:
        doc = Document()
        # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        origimg = gen_2b_unc(2, 0.1, t.a, t.ua)
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

        logger.warning(f"Testing {t.e} : a={t.a}±{t.ua}, b={t.b}±{t.ub} ----------------------------------------------")
        check_op_test(doc, t, expr, origimg)


def test_image_image_binops():
    """Test that binops work on image/image pairs, where the LHS image has an ROI on it."""

    pcot.setup()

    for t in binop_tests:
        doc = Document()
        # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        imgA = gen_2b_unc(2, 0.1, t.a, t.ua)
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

        logger.warning(f"Testing {t.e} : a={t.a}±{t.ua}, b={t.b}±{t.ub} ----------------------------------------------")
        check_op_test(doc, t, expr, imgA)


def test_image_image_binops_noroi():
    """test image/image operations without a region of interest."""

    pcot.setup()

    for t in binop_tests:
        doc = Document()
        # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        imgA = gen_2b_unc(2, 0.1, t.a, t.ua)
        doc.setInputDirect(0, imgA)
        nodeA = doc.graph.create("input 0")

        # node B is a 20x20 2-band image with 3±0.2 in band 0 and the given values in band 1.
        imgB = gen_2b_unc(3, 0.2, t.b, t.ub)
        doc.setInputDirect(1, imgB)
        nodeB = doc.graph.create("input 1")

        # just to check that DQ bits get OR-ed in, we set some DQ in the image.
        if t.e != "a|b" and t.e != "a&b":  # doesn't work with these, they handle dq differently
            imgA.dq[8, 8, 1] = dq.UNDEF

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
                edq = t.expected_dq | imgA.dq[y, x, 1]
                dqtest = dqv == edq

                if not (ntest and utest and dqtest):
                    logger.error(f"Error in binop test at pixel {x},{y} for expression {expr.expr}")
                    if not ntest:
                        logger.error(f"N expected {expected_n} got {n}")
                    if not utest:
                        logger.error(f"U expected {expected_u} got {u}")
                    if not dqtest:
                        logger.error(f"DQ expected {edq} got {dqv}")

                assert ntest and utest and dqtest


def test_dq_propagation_images():
    """Test that DQ is propagated correctly in the binary operators on images"""

    pcot.setup()

    def runtest(a, ua, adq, b, ub, bdq, e, expected_val, expected_unc, expected_dq):
        doc = Document()
        # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        imgA = gen_2b_unc(2, 0.1, a, ua, dq0=0, dq1=adq)
        doc.setInputDirect(0, imgA)
        nodeA = doc.graph.create("input 0")

        # node B is a 20x20 2-band image with 3±0.2 in band 0 and the given values in band 1.
        imgB = gen_2b_unc(3, 0.2, b, ub, dq0=0, dq1=bdq)
        doc.setInputDirect(1, imgB)
        nodeB = doc.graph.create("input 1")

        # and connect an expression node to rect and nodeB.
        expr = doc.graph.create("expr")
        expr.expr = e
        # this is where the connections are reversed.
        expr.connect(0, nodeA, 0, autoPerform=False)
        expr.connect(1, nodeB, 0, autoPerform=False)

        logger.warning(f"Testing {e} : a={a}±{ua}dq={adq}, b={b}±{ub}dq={bdq} --------------------------------------")

        doc.changed()
        img = expr.getOutput(0, Datum.IMG)  # has to be an image!
        assert img is not None

        expected_n = pytest.approx(expected_val)
        expected_u = pytest.approx(expected_unc)

        for x in range(0, 20):
            for y in range(0, 20):
                n = img.img[y, x, 1]
                u = img.uncertainty[y, x, 1]
                dqv = img.dq[y, x, 1]

                ntest = n == expected_n
                utest = u == expected_u
                dqtest = dqv == expected_dq

                if not (ntest and utest and dqtest):
                    logger.error(f"Error in binop test at pixel {x},{y} for expression {expr.expr}")
                    if not ntest:
                        logger.error(f"N expected {expected_n} got {n}")
                    if not utest:
                        logger.error(f"U expected {expected_u} got {u}")
                    if not dqtest:
                        logger.error(
                            f"DQ expected {dq.names(expected_dq, shownone=True)} got {dq.names(dqv, shownone=True)}")

                assert ntest and utest and dqtest

    # for each of these ops, and also checking the result...
    for op, res in [('+', 5), ('-', -1), ('*', 6), ('/', 0.66666666666), ('^', 8)]:
        e = f"a{op}b"
        # check no dq propagates
        runtest(2, 0, dq.NONE, 3, 0, dq.NONE, e, res, 0, dq.NONE)
        # check DQ on LHS propagates
        runtest(2, 0, dq.UNDEF | dq.NOUNCERTAINTY, 3, 0, dq.NONE, e, res, 0, dq.UNDEF | dq.NOUNCERTAINTY)
        # and on RHS
        runtest(2, 0, dq.NONE, 3, 0, dq.UNDEF | dq.NOUNCERTAINTY, e, res, 0, dq.UNDEF | dq.NOUNCERTAINTY)
        # and check both are ORed in.
        runtest(2, 0, dq.SAT, 3, 0, dq.UNDEF | dq.NOUNCERTAINTY, e, res, 0, dq.SAT | dq.UNDEF | dq.NOUNCERTAINTY)

    # min and max are different; the DQ comes from the side which "wins"
    runtest(2, 0, dq.SAT, 3, 0, dq.UNDEF, "a|b", 3, 0, dq.UNDEF)      # max operator, dq comes from b
    runtest(2, 0, dq.SAT, 3, 0, dq.UNDEF, "a&b", 2, 0, dq.SAT)      # min operator, dq comes from a

