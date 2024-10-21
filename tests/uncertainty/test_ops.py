"""Test binary and unary operators for uncertainty at the top (graph) level. Some
of these tests might seem redundant, because we also do them at the lower (Value) level.
But it's good to do some basic tests up here too.

If these tests fail, but those tests in basic/test_values.py pass, the
problem is probably in the nodes or expression parser.

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
    nodeV.params.val = float(v)
    nodeU.params.val = float(u)
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
    doc.run()
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

    doc.run()
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

    def __str__(self):
        """Annoyingly the output console can't handle unicode, so I can't use the ± here. Using | instead.
        Used to generate test names."""
        return f"{self.e}: a={self.n}|{self.u}|{dq.names(self.dq,True)},exp={self.expected_val}|{self.expected_unc}|{dq.names(self.expected_dq,True)}"


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
    UnopTest(0.3, 2, dq.SAT | dq.COMPLEX, "!a", 0.7, 2, dq.SAT | dq.COMPLEX),  # DQ must get passed through
]


@pytest.mark.parametrize("t", unop_tests, ids=lambda x: x.__str__())
def test_number_unops(t):
    """Test that unary operations in expr nodes on numbers with uncertainty work. In the case of
    unary negation and inverse, (- and !) the uncertainty is passed through unchanged"""
    pcot.setup()
    doc = Document()
    node = numberWithUncNode(doc, t.n, t.u, t.dq)
    expr = doc.graph.create("expr")
    expr.expr = t.e
    expr.connect(0, node, 0, autoPerform=False)
    doc.run()
    n = expr.getOutput(0, Datum.NUMBER)
    assert n is not None
    assert n.n == pytest.approx(t.expected_val)
    assert n.u == pytest.approx(t.expected_unc)
    assert n.dq == t.expected_dq


@pytest.mark.parametrize("t", unop_tests, ids=lambda x: x.__str__())
def test_image_unops(t):
    """Test that unary operations in expr nodes on images with uncertainty work. Also ensure that
    the operation only acts on areas covered by an ROI and that DQs are passed through."""
    pcot.setup()
    doc = Document()
    # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
    img = gen_2b_unc(2, 0.1, t.n, t.u, dq0=0, dq1=t.dq)
    # just to check that DQ bits get OR-ed in (or rather passed through), we set some (more) DQ in the image.
    img.dq[2, 2, 1] |= dq.COMPLEX
    img.dq[8, 8, 1] |= dq.UNDEF
    doc.setInputDirectImage(0, img)
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

    def __str__(self):
        """Annoyingly the output console can't handle unicode, so I can't use the ± here. Using | instead.
        Used to generate test names."""
        return f"{self.e}: a={self.a}|{self.ua}, b={self.b}|{self.ub}, exp={self.expected_val}|{self.expected_unc}{dq.names(self.expected_dq,True)}"


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
    BinopTest(0, 0, 20, 1, "a/b", 0, 0, dq.NONE),  # 0 / 20±anything = 0
    BinopTest(0, 0, 20, 2, "a/b", 0, 0, dq.NONE),  # 0 / 20±anything = 0
    BinopTest(3, 0.1, 10, 0.3, "a/b", 0.3, 0.0134536240470737, dq.NONE), # 3±0.1 / 10±0.3 0.3±0.0134536240470737
    BinopTest(0, 2, 20, 2, "a/b", 0, 0.1, dq.NONE),  # 0±2 / 20±2 = 0±0.1
    BinopTest(2, 0, 0, 0, "a/b", 0, 0, dq.DIVZERO),  # 2/0 = 0 but divzero flag set
    BinopTest(0, 0, 0, 0, "a/b", 0, 0, dq.DIVZERO | dq.UNDEF),  # 0/0 = 0 but divzero and undef set

    BinopTest(10, 2, 2, 3, "a^b", 100, 691.932677319881, dq.NONE),  # 10±2 ^ 2±3 = 100±691.932677319881
    BinopTest(3, 0.1, 2, 0.02, "a^b", 9, 0.631747691986546, dq.NONE),  # 3±0.1 ^ 2±0.02 = 9±0.631747691986546

    # 2.45±0.12 ^ 0.76±0.072 = 1.97590574573865±0.147178832101251
    BinopTest(2.45, 0.12, 0.76, 0.072, "a^b", 1.97590574573865, 0.147178832101251, dq.NONE),

    BinopTest(0, 2, 1, 3, "a^b", 0, 2, dq.NONE),  # 0±2 ^ 1±3 = 0±2 (i.e. 0^1 equals 0, with the uncertainty of the 0)
    BinopTest(0, 2, 0, 3, "a^b", 1, 0, dq.NONE),  # 0±2 ^ 0±3 = 1±0 (i.e. 0^0 = 1, uncertainties ignored)
    BinopTest(0, 2, -2, 3, "a^b", 0, 0, dq.UNDEF),  # 0±2 ^ -2±3 = 0±0 (actually UNDEF, can't raise zero to -ve power)
    BinopTest(0, 2, 0.2, 3, "a^b", 0, 0, dq.NONE),  # 0±2 ^ 0.2±3 = 0±0 (i.e. 0^n = 0 where n>0 and n!=1)
    BinopTest(0, 2, 4, 3, "a^b", 0, 0, dq.NONE),  # 0±2 ^ 4±3 = 0±0 (i.e. 0^n = 0 where n>0 and n!=1)

    BinopTest(1, 2, 4, 3, "a|b", 4, 3, dq.NONE),  # OR operator finds the maximum
    BinopTest(1, 2, 4, 3, "a&b", 1, 2, dq.NONE),  # AND operator finds the minimum

]


@pytest.mark.filterwarnings("ignore:invalid value")
@pytest.mark.filterwarnings("ignore:divide by zero")
@pytest.mark.parametrize("t", binop_tests, ids=lambda x: x.__str__())
def test_number_number_binops(t):
    """Test that binary operations in expr nodes on numbers with uncertainty work."""
    pcot.setup()

    """(a,ua) and (b,ub) are scalar inputs with uncertainties. E is the expression."""
    doc = Document()
    nodeA = numberWithUncNode(doc, t.a, t.ua)
    nodeB = numberWithUncNode(doc, t.b, t.ub)
    expr = doc.graph.create("expr")
    expr.expr = t.e
    expr.connect(0, nodeA, 0, autoPerform=False)
    expr.connect(1, nodeB, 0, autoPerform=False)

    logger.warning(f"Testing {t.e} : a={t.a}±{t.ua}, b={t.b}±{t.ub} ----------------------------------------------")
    doc.run()
    n = expr.getOutput(0, Datum.NUMBER)
    assert n is not None
    assert n.n == pytest.approx(t.expected_val)
    assert n.u == pytest.approx(t.expected_unc)
    assert n.dq == t.expected_dq


@pytest.mark.filterwarnings("ignore:invalid value")
@pytest.mark.filterwarnings("ignore:divide by zero")
@pytest.mark.parametrize("t", binop_tests, ids=lambda x: x.__str__())
def test_number_image_binops(t):
    """Test than binops in expr nodes on numbers and images work, with the image on the RHS. We want to
    ensure that the part outside an ROI are unchanged."""
    pcot.setup()
    doc = Document()
    # node A just numeric.
    nodeA = numberWithUncNode(doc, t.a, t.ua)
    # node B is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
    origimg = gen_2b_unc(2, 0.1, t.b, t.ub)

    doc.setInputDirectImage(0, origimg)
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


@pytest.mark.parametrize("t", binop_tests, ids=lambda x: x.__str__())
def test_image_number_binops(t):
    """Test than binops in expr nodes on images and numbers work, with the image on the LHS. We want to
    ensure that the part outside an ROI are unchanged.
    """
    pcot.setup()

    doc = Document()
    # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
    origimg = gen_2b_unc(2, 0.1, t.a, t.ua)
    doc.setInputDirectImage(0, origimg)
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


@pytest.mark.parametrize("t", binop_tests, ids=lambda x: x.__str__())
def test_image_image_binops(t):
    """Test that binops work on image/image pairs, where the LHS image has an ROI on it."""

    pcot.setup()
    doc = Document()
    # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
    imgA = gen_2b_unc(2, 0.1, t.a, t.ua)
    doc.setInputDirectImage(0, imgA)
    nodeA = doc.graph.create("input 0")
    # which feeds into a rect ROI
    rect = doc.graph.create("rect")
    rect.roi.set(5, 5, 10, 10)  # set the rectangle to be at 5,5 extending 10x10
    rect.connect(0, nodeA, 0, autoPerform=False)

    # node B is a 20x20 2-band image with 3±0.2 in band 0 and the given values in band 1.
    imgB = gen_2b_unc(3, 0.2, t.b, t.ub)
    doc.setInputDirectImage(1, imgB)
    nodeB = doc.graph.create("input 1")
    # and connect an expression node to rect and nodeB.
    expr = doc.graph.create("expr")
    expr.expr = t.e
    # this is where the connections are reversed.
    expr.connect(0, rect, 0, autoPerform=False)
    expr.connect(1, nodeB, 0, autoPerform=False)

    logger.warning(f"Testing {t.e} : a={t.a}±{t.ua}, b={t.b}±{t.ub} ----------------------------------------------")
    check_op_test(doc, t, expr, imgA)


@pytest.mark.parametrize("t", binop_tests, ids=lambda x: x.__str__())
def test_image_image_binops_noroi(t):
    """test image/image operations without a region of interest."""
    pcot.setup()
    doc = Document()
    # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
    imgA = gen_2b_unc(2, 0.1, t.a, t.ua)
    doc.setInputDirectImage(0, imgA)
    nodeA = doc.graph.create("input 0")

    # node B is a 20x20 2-band image with 3±0.2 in band 0 and the given values in band 1.
    imgB = gen_2b_unc(3, 0.2, t.b, t.ub)
    doc.setInputDirectImage(1, imgB)
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

    doc.run()
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


# generate test params for DQ propagation


@dataclass
class DQPropTest:
    a_scalar: bool
    b_scalar: bool
    a: float  # Nominal value of A
    ua: float  # uncertainty of A
    dqa: np.uint16  # dq of a
    b: float  # nominal value of B
    ub: float  # uncertainty of B
    dqb: np.uint16  # dq of b

    e: str  # binary expression in A and B (e.g. "a+b")
    expected_val: float  # expected nominal result
    expected_unc: float  # expected uncertainty of result
    expected_dq: np.uint16  # expected DQ in result

    def __str__(self):
        """Annoyingly the output console can't handle unicode, so I can't use the ± here. Using | instead.
        Used to generate test names."""
        return f"{'scal' if self.a_scalar else 'img'}|{'scal' if self.b_scalar else 'img'} " + \
            f"{self.e}: a={self.a}|{self.ua}|{self.dqa}, " + \
            f"b={self.b}|{self.ub}|{self.dqb}, " + \
            f"exp={self.expected_val}|{self.expected_unc}|{dq.names(self.expected_dq,True)}"


dq_prop_tests = []
for a_is_scalar in (True, False):
    for b_is_scalar in (True, False):
        for op, res in [('+', 5), ('-', -1), ('*', 6), ('/', 0.66666666666), ('^', 8)]:
            e = f"a{op}b"
            # check DQ on LHS propagates
            dq_prop_tests.append(
                DQPropTest(a_is_scalar, b_is_scalar, 2, 0, dq.UNDEF | dq.NOUNCERTAINTY, 3, 0, dq.NONE,
                           e, res, 0, dq.UNDEF | dq.NOUNCERTAINTY))
            # check no dq propagates
            dq_prop_tests.append(
                DQPropTest(a_is_scalar, b_is_scalar, 2, 0, dq.NONE, 3, 0, dq.NONE, e, res, 0, dq.NONE))
            # and on RHS
            dq_prop_tests.append(
                DQPropTest(a_is_scalar, b_is_scalar, 2, 0, dq.NONE, 3, 0, dq.UNDEF | dq.NOUNCERTAINTY, e,
                           res, 0, dq.UNDEF | dq.NOUNCERTAINTY))
            # and check both are ORed in.
            dq_prop_tests.append(
                DQPropTest(a_is_scalar, b_is_scalar, 2, 0, dq.SAT, 3, 0, dq.UNDEF | dq.NOUNCERTAINTY, e,
                           res, 0, dq.SAT | dq.UNDEF | dq.NOUNCERTAINTY))

        # min and max are different; the DQ comes from the side which "wins"
        # max operator, dq comes from b
        dq_prop_tests.append(DQPropTest(a_is_scalar, b_is_scalar, 2, 0, dq.SAT, 3, 0, dq.UNDEF, "a|b", 3, 0, dq.UNDEF))
        # min operator, dq comes from a
        dq_prop_tests.append(DQPropTest(a_is_scalar, b_is_scalar, 2, 0, dq.SAT, 3, 0, dq.UNDEF, "a&b", 2, 0, dq.SAT))


@pytest.mark.parametrize("t", dq_prop_tests, ids=lambda x: x.__str__())
def test_dq_propagation_images(t):
    """Test that DQ is propagated correctly in the binary operators on images"""

    pcot.setup()

    doc = Document()
    if t.a_scalar:
        nodeA = doc.graph.create("expr")
        nodeA.expr = f"v({t.a},{t.ua},{t.dqa})"
    else:
        # node A is a 20x20 2-band image with 2±0.1 in band 0 and the given values in band 1.
        imgA = gen_2b_unc(2, 0.1, t.a, t.ua, dq0=0, dq1=t.dqa)
        doc.setInputDirectImage(0, imgA)
        nodeA = doc.graph.create("input 0")

    if t.b_scalar:
        nodeB = doc.graph.create("expr")
        nodeB.expr = f"v({t.b},{t.ub},{t.dqb})"
    else:
        # node B is a 20x20 2-band image with 3±0.2 in band 0 and the given values in band 1.
        imgB = gen_2b_unc(3, 0.2, t.b, t.ub, dq0=0, dq1=t.dqb)
        doc.setInputDirectImage(1, imgB)
        nodeB = doc.graph.create("input 1")

    # and connect an expression node to rect and nodeB.
    expr = doc.graph.create("expr")
    expr.expr = t.e
    # this is where the connections are reversed.
    expr.connect(0, nodeA, 0, autoPerform=False)
    expr.connect(1, nodeB, 0, autoPerform=False)

    expected_n = pytest.approx(t.expected_val)
    expected_u = pytest.approx(t.expected_unc)

    doc.run()

    if t.a_scalar and t.b_scalar:
        val = expr.getOutput(0, Datum.NUMBER)
        assert val is not None
        assert val.n == expected_n
        assert val.u == expected_u
        assert val.dq == t.expected_dq
    else:
        img = expr.getOutput(0, Datum.IMG)  # has to be an image!
        assert img is not None

        for x in range(0, 20):
            for y in range(0, 20):
                n = img.img[y, x, 1]
                u = img.uncertainty[y, x, 1]
                dqv = img.dq[y, x, 1]

                ntest = n == expected_n
                utest = u == expected_u
                dqtest = dqv == t.expected_dq

                if not (ntest and utest and dqtest):
                    logger.error(f"Error in binop test at pixel {x},{y} for expression {expr.expr}")
                    if not ntest:
                        logger.error(f"N expected {expected_n} got {n}")
                    if not utest:
                        logger.error(f"U expected {expected_u} got {u}")
                    if not dqtest:
                        logger.error(
                            f"DQ expected {dq.names(t.expected_dq, shownone=True)} got {dq.names(dqv, shownone=True)}")

                assert ntest and utest and dqtest

