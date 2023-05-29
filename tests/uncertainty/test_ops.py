"""Test binary and unary operators for uncertainty"""
from math import sqrt

import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document


def numberWithUncNode(doc, v,u):
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


def test_number_number_ops():
    pcot.setup()

    def runop(a, ua, b, ub, e, expected_val, expected_unc):
        """(a,ua) and (b,ub) are scalar inputs with uncertainties. E is the expression."""
        doc = Document()
        nodeA = numberWithUncNode(doc, a, ua)
        nodeB = numberWithUncNode(doc, b, ub)

        expr = doc.graph.create("expr")
        expr.expr = e
        expr.connect(0, nodeA, 0, autoPerform=False)
        expr.connect(1, nodeB, 0, autoPerform=False)

        doc.changed()
        n = expr.getOutput(0, Datum.NUMBER)
        assert n is not None
        assert n.n == pytest.approx(expected_val)
        assert n.u == pytest.approx(expected_unc)

    # these are all generated using the uncertainties package

    runop(10, 0, 20, 0, "a+b", 30, 0)                   # 10 + 20 = 30
    runop(10, 2, 20, 5, "a+b", 30, sqrt(2*2+5*5))       # 10±2 + 20±5 = 30±sqr(2^2+5^2)

    runop(10, 0, 20, 0, "a-b", -10, 0)                   # 10 - 20 = 30
    runop(10, 2, 20, 5, "a-b", -10, sqrt(2*2+5*5))       # 10±2 + 20±5 = 30±sqr(2^2+5^2)

    runop(10, 0, 20, 0, "a*b", 200, 0)                   # 10 * 20 = 200
    runop(10, 2, 20, 3, "a*b", 200, 50.0)               # 10±2 * 20±3 = 200±50
    runop(20, 3, 10, 2, "a*b", 200, 50.0)               # 20±3 * 20±2 = 200±50
    runop(10, 3, 20, 2, "a*b", 200, 63.24555)               # 10±3 * 20±2 = 200±63.24555 (approx)
    runop(10, 3, -20, 2, "a*b", -200, 63.24555)               # 10±3 * -20±2 = -200±63.24555 (approx)
