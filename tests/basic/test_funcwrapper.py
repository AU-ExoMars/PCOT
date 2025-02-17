"""
Test the functions which are wrapped with funcWrapper. Some testing is also done in graphs to test the ordering
"""
import dataclasses
import math
from typing import Tuple

import numpy as np
import pytest

import pcot
from fixtures import genrgb
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document
from pcot.sources import nullSource
from pcot.value import Value
from unaryfunctests import func_tests, FuncTest


@pytest.mark.parametrize("t", func_tests, ids=lambda x: x.__str__())
def test_funcwrapper(t: FuncTest):
    pcot.setup()
    doc = Document()

    i = doc.graph.create("input 0")
    inp = Value(*t.inp)
    doc.setInputDirect(0, Datum(Datum.NUMBER, inp, nullSource))

    e = doc.graph.create("expr")
    e.params.expr = t.expr
    e.connect(0, i, 0)

    doc.run()

    res = e.getOutput(0, Datum.NUMBER)
    assert res is not None
    exp = Value(*t.exp)
    assert res.approxeq(exp)
