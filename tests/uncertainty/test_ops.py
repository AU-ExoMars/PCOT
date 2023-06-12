"""Test binary and unary operators for uncertainty at the top (graph) level. Some
of these tests might seem redundant, because we also do them at the lower (Value) level.
But it's good to do some basic tests up here too.

There's a very handy calculator with uncertainties at https://uncertaintycalculator.com/

"""
from math import sqrt

import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document


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
    pcot.setup()

    def runop(a, ua, e, expected_val, expected_unc):
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
    runop(-1, 2, "!a", 2, 2)    # a terrible thing to do, this is really an error.

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

    # these test values are all generated using the uncertainties package or the uncertainty calculator
    # at https://uncertaintycalculator.com/

    runop(10, 0, 20, 0, "a+b", 30, 0)  # 10 + 20 = 30
    runop(10, 2, 20, 5, "a+b", 30, sqrt(2 * 2 + 5 * 5))  # 10±2 + 20±5 = 30±sqr(2^2+5^2)

    runop(10, 0, 20, 0, "a-b", -10, 0)  # 10 - 20 = 30
    runop(10, 2, 20, 5, "a-b", -10, sqrt(2 * 2 + 5 * 5))  # 10±2 + 20±5 = 30±sqr(2^2+5^2)

    runop(10, 0, 20, 0, "a*b", 200, 0)  # 10 * 20 = 200
    runop(10, 2, 20, 3, "a*b", 200, 50.0)  # 10±2 * 20±3 = 200±50
    runop(20, 3, 10, 2, "a*b", 200, 50.0)  # 20±3 * 20±2 = 200±50
    runop(10, 3, 20, 2, "a*b", 200, 63.24555)  # 10±3 * 20±2 = 200±63.24555 (approx)
    runop(10, 3, -20, 2, "a*b", -200, 63.24555)  # 10±3 * -20±2 = -200±63.24555 (approx)

    runop(10, 0, 20, 0, "a/b", 0.5, 0)
    runop(10, 0, 20, 2, "a/b", 0.5, 0.05)  # 10 / 20±2 = 200±0.05
    runop(10, 2, 20, 0, "a/b", 0.5, 0.1)  # 10±2 / 20 = 200±0.1
    runop(10, 2, 20, 3, "a/b", 0.5, 0.125)  # 10±2 / 20±3 = 200±0.125
    runop(10, 3, 20, 2, "a/b", 0.5, 0.15811388)  # 10±3 / 20±2 = 200±0.158 (approx)
    runop(0, 0, 20, 2, "a/b", 0, 0)  # 0 / 20±2 = 0
    runop(0, 2, 20, 2, "a/b", 0, 0.1)  # 0±2 / 20±2 = 0±0.1

    runop(10, 2, 2, 3, "a^b", 100, 691.932677319881)  # 10±2 ^ 2±3 = 100±691.932677319881

    runop(0, 2, 1, 3, "a^b", 0, 2)  # 0±2 ^ 1±3 = 0±2 (i.e. 0^1 equals 0, with the uncertainty of the 0)
    runop(0, 2, 0, 3, "a^b", 1, 0)  # 0±2 ^ 0±3 = 1±0 (i.e. 0^0 = 1, uncertainties ignored)
    runop(0, 2, -2, 3, "a^b", 0, 0)  # 0±2 ^ -2±3 = 0±0 (actually "invalid", can't raise zero to -ve power)
    runop(0, 2, 0.2, 3, "a^b", 0, 0)  # 0±2 ^ 0.2±3 = 0±0 (i.e. 0^n = 0 where n>0 and n!=1)
    runop(0, 2, 4, 3, "a^b", 0, 0)  # 0±2 ^ 4±3 = 0±0 (i.e. 0^n = 0 where n>0 and n!=1)

    runop(1, 2, 4, 3, "a|b", 4, 3)  # OR operator finds the maximum
    runop(1, 2, 4, 3, "a&b", 1, 2)  # AND operator finds the minimum
