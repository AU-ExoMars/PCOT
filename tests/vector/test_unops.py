"""
Test unary operations and builtin vector funcs (sin, cos, sqrt etc.) on vector values.
Quite a lot of these tests are completely redundant with the tests in test_values.py,
but the use-case here is slightly different.
"""
import importlib

import pytest

import pcot
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document
from pcot.sources import nullSource
from pcot.value import Value
from unaryfunctests import func_tests, FuncTest


def test_arithmetic_negation():
    v = Value([2, 3], 0.1, dq.TEST)
    r = -v
    assert r == Value([-2, -3], 0.1, dq.TEST)


def test_logical_negation():
    v = Value([1, 0, 0.5], [0.1, 0.2, 0.3], dq.TEST)
    r = ~v
    assert r == Value([0, 1, 0.5], [0.1, 0.2, 0.3], dq.TEST)


@pytest.mark.parametrize("t", func_tests, ids=lambda x: x.__str__())
def test_funcwrapper(t: FuncTest):
    """This is very similar to the test in test_funcwrapper.py, but we're testing the unary functions on vectors.
    It still has to create a graph and use the expression node, thus using the wrapper mechanism in Datum."""

    # this is really the only difference - we have to create a vector value
    def expand_to_vector(tup):
        n, u, d = tup
        n = [n, n, n]
        v = Value(n, u, d)
        assert v.n.shape == (3,)
        assert v.u.shape == (3,)
        assert v.dq.shape == (3,)
        return v

    inp = expand_to_vector(t.inp)
    exp = expand_to_vector(t.exp)

    pcot.setup()
    doc = Document()

    i = doc.graph.create("input 0")
    doc.setInputDirect(0, Datum(Datum.NUMBER, inp, nullSource))

    e = doc.graph.create("expr")
    e.params.expr = t.expr
    e.connect(0, i, 0)

    doc.run()

    res = e.getOutput(0, Datum.NUMBER)
    assert res is not None
    assert res.approxeq(exp)

