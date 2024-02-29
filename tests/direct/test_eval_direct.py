"""
Test "direct" use of the expression evaluator, outside an expr node
"""
import numpy as np

import pcot
from pcot.datum import Datum
from pcot.expressions import ExpressionEvaluator
from pcot.sources import nullSourceSet
from pcot.value import Value


def test_evaluator_inline():
    """Test the evaluator in "inline" mode with both images and numbers"""
    pcot.setup()

    e = ExpressionEvaluator()
    r = e.run("sqrt(a+b+2)",
              {
                  'a': Datum(Datum.NUMBER, Value(10.0, 0.1), nullSourceSet),
                  'b': lambda: Datum(Datum.NUMBER, Value(4.0, 0.2), nullSourceSet)
              })
    v = r.get(Datum.NUMBER)
    assert np.allclose(4.0, v.n)
    assert np.allclose(0.02795085, v.u)
    assert v.dq == 0
