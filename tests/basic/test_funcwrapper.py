"""
Test the functions which are wrapped with funcWrapper. Some testing is also done in graphs to test the ordering
"""
import dataclasses
import math

import pytest

import pcot
from fixtures import genrgb
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document
from pcot.sources import nullSource
from pcot.value import Value


@dataclasses.dataclass
class FuncTest:
    expr: str  # test expression in a
    inp: Value  # input value
    exp: Value  # expected result

    def __str__(self):
        return f"{self.expr}: in={self.inp.brief()}, exp={self.exp.brief()}"


func_tests = [
    FuncTest("sqrt(a)", Value(4, 0, dq.NONE), Value(2, 0, dq.NONE)),
    FuncTest("sqrt(a)", Value(2, 0, dq.NONE), Value(math.sqrt(2), 0, dq.NONE)),
    FuncTest("sqrt(a)", Value(0, 0, dq.NONE), Value(0, 0, dq.NONE)),
    FuncTest("sqrt(a)", Value(-1, 0, dq.NONE), Value(0, 0, dq.COMPLEX)),
    FuncTest("sqrt(a)", Value(-1, 0, dq.TEST), Value(0, 0, dq.COMPLEX | dq.TEST)),

]


@pytest.mark.parametrize("t", func_tests, ids=lambda x: x.__str__())
def test_funcwrapper(t: FuncTest):
    pcot.setup()
    doc = Document()

    i = doc.graph.create("input 0")
    doc.setInputDirect(0, Datum(Datum.NUMBER, t.inp, nullSource))

    e = doc.graph.create("expr")
    e.expr = t.expr
    e.connect(0, i, 0)

    doc.changed()

    res = e.getOutput(0, Datum.NUMBER)
    assert res is not None
    assert res.approxeq(t.exp)
