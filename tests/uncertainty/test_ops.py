"""Test binary and unary operators for uncertainty"""
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
    expr.connect(0, nodeU, 0)
    expr.connect(1, nodeV, 0)
    return expr


def test_make_unc():
    """Test that the scalar+uncertainty generator works"""
    pcot.setup()
    doc = Document()
    node = numberWithUncNode(doc, 1, 3)
    doc.changed()
    n = node.getOutput(0, Datum.NUMBER)
    pytest.fail("Need to get nom,std out of this")
    assert n is not None


def test_number_number_ops():
    pcot.setup()

    def runop(a, ua, b, ub, e, expected_val, expected_unc):
        """(a,ua) and (b,ub) are scalar inputs with uncertainties. E is the expression."""
        doc = Document()
        nodeA = numberWithUncNode(doc, a, ua)
        nodeB = numberWithUncNode(doc, a, ub)

        expr = doc.graph.create("expr")
        expr.connect(0, nodeA, 0)
        expr.connect(1, nodeB, 0)
