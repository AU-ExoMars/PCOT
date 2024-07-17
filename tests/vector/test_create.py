import numpy as np

import pcot
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document
from pcot.xform import XFormException


def test_noargs():
    """Test creating a vector with [] notation but no contents - should fail"""
    pcot.setup()
    doc = Document()

    # this should fail
    n = doc.graph.create("expr")
    n.expr = "[]"

    doc.run()
    assert isinstance(n.error, XFormException)
    assert "syntax error" in n.error.message


def test_one_element():
    """Test creating a vector with one element"""
    pcot.setup()
    doc = Document()

    n = doc.graph.create("expr")
    n.expr = "[1]"

    doc.run()
    assert n.getOutput(0, Datum.NUMBER).n.shape == (1,)
    assert n.getOutput(0, Datum.NUMBER).n[0] == 1


def test_two_elements():
    """Test creating a vector with two elements, one of which has uncertainty"""
    pcot.setup()
    doc = Document()

    n = doc.graph.create("expr")
    n.expr = "[1, v(2,0.1)]"

    doc.run()
    assert n.getOutput(0, Datum.NUMBER).n.shape == (2,)
    assert n.getOutput(0, Datum.NUMBER).n[0] == 1
    assert n.getOutput(0, Datum.NUMBER).u[0] == 0
    assert n.getOutput(0, Datum.NUMBER).dq[0] == dq.NONE

    assert n.getOutput(0, Datum.NUMBER).n[1] == 2
    assert np.isclose(n.getOutput(0, Datum.NUMBER).u[1], 0.1)
    assert n.getOutput(0, Datum.NUMBER).dq[1] == dq.NONE
