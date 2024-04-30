"""
Test the functions which are wrapped with funcWrapper. Some testing is also done in graphs to test the ordering
"""
import dataclasses
import math

import numpy as np
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

    FuncTest("sqrt(a)", Value(2, 0.1, dq.NONE), Value(math.sqrt(2), 0.0353553390593272, dq.NONE)),
    FuncTest("sqrt(a)", Value(4, 0.1, dq.NONE), Value(2, 0.025, dq.NONE)),

    FuncTest("sin(a)", Value(2, 0.1, dq.NONE), Value(0.9092974, 0.0416147, dq.NONE)),
    FuncTest("sin(a)", Value(-1.2, 0.2, dq.NONE), Value(-0.932039085967226, 0.0724715508953348, dq.NONE)),

    FuncTest("cos(a)", Value(2, 0.1, dq.NONE), Value(-0.416146836547142, 0.0909297426825682, dq.NONE)),
    FuncTest("cos(a)", Value(-1.2, 0.2, dq.NONE), Value(0.362357754476674, 0.186407817193445, dq.NONE)),

    FuncTest("tan(a)", Value(2, 0.1, dq.NONE), Value(-2.18503986326152, 0.577439920404191, dq.NONE)),
    FuncTest("tan(a)", Value(-2, 0.1, dq.NONE), Value(2.18503986326152, 0.577439920404191, dq.NONE)),
    # just illustrates that we don't get the tan(pi/2) case easily!
    FuncTest("tan(a)", Value(np.pi / 2.0, 0.1, dq.NONE), Value(-22877332.0, 9999999827968.0, dq.DIVZERO)),

    FuncTest("abs(a)", Value(0.2, 0, dq.NONE), Value(0.2, 0, dq.NONE)),
    FuncTest("abs(a)", Value(-0.2, 0, dq.NONE), Value(0.2, 0, dq.NONE)),
    FuncTest("abs(a)", Value(0.2, 0.1, dq.NONE), Value(0.2, 0.1, dq.NONE)),
    FuncTest("abs(a)", Value(-0.2, 0.1, dq.NONE), Value(0.2, 0.1, dq.NONE)),
    FuncTest("abs(a)", Value(-4.321, 0.12, dq.TEST | dq.SAT), Value(4.321, 0.12, dq.TEST | dq.SAT)),

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

    doc.run()

    res = e.getOutput(0, Datum.NUMBER)
    assert res is not None
    assert res.approxeq(t.exp)
