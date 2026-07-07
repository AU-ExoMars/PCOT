"""
More test of uncertainty in powers
"""

import logging

import pcot
from pcot import dq
from pcot.document import Document
from pcot.value import Value
from unc_fixtures import gen_2b_unc
from uncertainty.test_ops import check_op_test, numberWithUncNode, BinopTest

logger = logging.getLogger(__name__)


def test_neg_b():
    a = Value(0,0.2)
    b = Value(-2,0.3)
    r = a**b
    assert r == Value(0,0,dq.UNDEF)


def test_square_root_neg():
    a = Value(-1)
    b = Value(0.5)
    r = a**b
    assert r.dq == dq.COMPLEX|dq.NOUNCERTAINTY
    assert r.n == 0
    assert r.u == 0


def test_square_root_neg_unc():
    a = Value(-1)
    b = Value(0.5)
    r = a**b
    assert r.dq == dq.COMPLEX|dq.NOUNCERTAINTY
    assert r.n == 0
    assert r.u == 0


def test_image_number_square_root_neg():
    """Test than binops in expr nodes on images and numbers work, with the image on the LHS. We want to
    ensure that the part outside an ROI are unchanged.
    """
    pcot.setup()

    t = BinopTest(-1, 0, 0.5, 0, "a^b", 0, 0, dq.COMPLEX)

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
    expr.params.expr = t.e
    # this is where the connections are reversed.
    expr.connect(0, rect, 0, autoPerform=False)
    expr.connect(1, nodeB, 0, autoPerform=False)

    logger.warning(f"Testing {t.e} : a={t.a}±{t.ua}, b={t.b}±{t.ub} ----------------------------------------------")
    check_op_test(doc, t, expr, origimg)


