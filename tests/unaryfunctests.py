"""
A list of unary function tests we can use.
Run from basic/test_funcwrapper and vector/test_unops.
"""

import dataclasses
import math
from typing import Tuple

import numpy as np

from pcot import dq
from pcot.value import Value


@dataclasses.dataclass
class FuncTest:
    """A test of a function. These are expressed as tuples rather than Values so we can use them
    in different ways - for example, creating a vector Value or a scalar Value."""
    expr: str  # test expression in a
    inp: Tuple[float, float, float]  # input value
    exp: Tuple[float, float, float]  # expected result

    def __str__(self):
        n1, u1, d1 = self.inp
        n2, u2, d2 = self.exp
        inp = Value(n1, u1, d1)
        exp = Value(n2, u2, d2)
        return f"{self.expr}: in={inp.brief_internal_repr()}, exp={exp.brief_internal_repr()}"


func_tests = [
    FuncTest("sqrt(a)", (4, 0, dq.NONE), (2, 0, dq.NONE)),
    FuncTest("sqrt(a)", (2, 0, dq.NONE), (math.sqrt(2), 0, dq.NONE)),
    FuncTest("sqrt(a)", (0, 0, dq.NONE), (0, 0, dq.NONE)),
    FuncTest("sqrt(a)", (-1, 0, dq.NONE), (0, 0, dq.COMPLEX)),
    FuncTest("sqrt(a)", (-1, 0, dq.TEST), (0, 0, dq.COMPLEX | dq.TEST)),

    FuncTest("sqrt(a)", (2, 0.1, dq.NONE), (math.sqrt(2), 0.0353553390593272, dq.NONE)),
    FuncTest("sqrt(a)", (4, 0.1, dq.NONE), (2, 0.025, dq.NONE)),

    FuncTest("sin(a)", (2, 0.1, dq.NONE), (0.9092974, 0.0416147, dq.NONE)),
    FuncTest("sin(a)", (-1.2, 0.2, dq.NONE), (-0.932039085967226, 0.0724715508953348, dq.NONE)),

    FuncTest("cos(a)", (2, 0.1, dq.NONE), (-0.416146836547142, 0.0909297426825682, dq.NONE)),
    FuncTest("cos(a)", (-1.2, 0.2, dq.NONE), (0.362357754476674, 0.186407817193445, dq.NONE)),

    FuncTest("tan(a)", (2, 0.1, dq.NONE), (-2.18503986326152, 0.577439920404191, dq.NONE)),
    FuncTest("tan(a)", (-2, 0.1, dq.NONE), (2.18503986326152, 0.577439920404191, dq.NONE)),
    # just illustrates that we don't get the tan(pi/2) case easily!
    FuncTest("tan(a)", (np.pi / 2.0, 0.1, dq.NONE), (-22877332.0, 9999999827968.0, dq.DIVZERO)),

    FuncTest("abs(a)", (0.2, 0, dq.NONE), (0.2, 0, dq.NONE)),
    FuncTest("abs(a)", (-0.2, 0, dq.NONE), (0.2, 0, dq.NONE)),
    FuncTest("abs(a)", (0.2, 0.1, dq.NONE), (0.2, 0.1, dq.NONE)),
    FuncTest("abs(a)", (-0.2, 0.1, dq.NONE), (0.2, 0.1, dq.NONE)),
    FuncTest("abs(a)", (-4.321, 0.12, dq.TEST | dq.SAT), (4.321, 0.12, dq.TEST | dq.SAT)),

]
