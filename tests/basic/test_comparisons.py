"""
Test the comparison operators in expr nodes
Tests on images are done as graph tests in comp_image .. .pcot
"""
import dataclasses

import numpy as np
import pytest

import pcot
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document


@dataclasses.dataclass
class CompTest:
    a: float
    op: str
    b: float
    res: bool


comp_tests = [
    CompTest(1, "<", 0, False),
    CompTest(0, ">", 1, False),
    CompTest(1, ">", 0, True),
    CompTest(0, "<", 1, True),
    CompTest(10, "<", 11, True),
    CompTest(10, ">", 11, False),
    CompTest(-11, ">", 10, False),
    CompTest(-11, "<", 10, True),
]


@pytest.mark.parametrize("t", comp_tests, ids=lambda x: f"{x.a}{x.op}{x.b}=={x.res}")
def test_comps_scalar(t):
    """Test comparison operators in scalars"""
    pcot.setup()
    doc = Document()
    expr = doc.graph.create("expr")
    expr.params.expr = f"{t.a}{t.op}{t.b}"

    doc.run()
    out = expr.getOutputDatum(0)
    assert out.tp == Datum.NUMBER
    v = out.get(Datum.NUMBER)
    assert v.n ==(1.0 if t.res else 0.0)
    assert v.u == 0.0
    assert v.dq == dq.NOUNCERTAINTY


@pytest.mark.parametrize("t", comp_tests, ids=lambda x: f"{x.a}{x.op}{x.b}=={x.res}")
def test_comps_vector(t):
    """Test comparison operators in expr nodes, using vectors. We actually test the test
    and its inverse (i.e. a op b and b op a) on two halves of a single vector."""
    pcot.setup()
    doc = Document()
    expr = doc.graph.create("expr")

    # we'll make two vectors, one will be [a,a,a,a,b,b,b,b] and the other [b,b,b,b,a,a,a,a]
    avec = [t.a] * 4 + [t.b] * 4
    bvec = [t.b] * 4 + [t.a] * 4

    def tostr(vec):
        return f"[{','.join([str(y) for y in vec])}]"

    expr.params.expr = f"{tostr(avec)}{t.op}{tostr(bvec)}"
    doc.run()
    out = expr.getOutputDatum(0)
    assert out.tp == Datum.NUMBER
    v = out.get(Datum.NUMBER)

    # the result should be res for the first four entries, and not res for the rest.

    resvec = np.array([t.res] * 4 + [1-t.res] * 4, dtype=np.float32)

    assert np.allclose(v.n, resvec)
    assert np.allclose(v.u, 0.0)
    assert np.all(v.dq == dq.NOUNCERTAINTY)


