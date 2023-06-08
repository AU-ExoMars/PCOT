import math

import pytest

from pcot import dq
from pcot.utils.ops import OpData


def test_approx():
    assert OpData(0, 0).approxeq(OpData(0, 0))
    assert OpData(1, 0).approxeq(OpData(1, 0))
    assert not OpData(1, 0).approxeq(OpData(0, 0))
    assert not OpData(0, 1).approxeq(OpData(0, 0))
    assert not OpData(0, 0).approxeq(OpData(1, 0))
    assert not OpData(0, 0).approxeq(OpData(0, 1))
    assert not OpData(0, 0.00001).approxeq(OpData(0, 0))


def test_equality_scalars():
    a = OpData(0, 0)
    assert a == OpData(0, 0)
    assert a != OpData(1, 0)
    assert a != OpData(0, 1)
    assert OpData(0, 0, dq.UNDEF) != OpData(0, 0)
    assert OpData(0, 0, dq.BAD) != OpData(0, 0, dq.UNDEF)
    assert a == a


def test_addition_scalars():
    assert OpData(2, 0) + OpData(3, 0) == OpData(5, 0)
    assert OpData(3, 0) + OpData(3, 0) != OpData(5, 0)
    assert OpData(2, 3) + OpData(7, 4) == OpData(9, 5)
    assert OpData(2, 4) + OpData(7, 3) == OpData(9, 5)


def test_subtraction_scalars():
    assert OpData(2, 0) - OpData(3, 0) == OpData(-1, 0)
    assert OpData(3, 0) - OpData(2, 0) == OpData(1, 0)
    assert OpData(2, 3) - OpData(7, 4) == OpData(-5, 5)
    assert OpData(2, 4) - OpData(7, 3) == OpData(-5, 5)


def test_multiplication_scalars():
    assert OpData(2, 0) * OpData(3, 0) == OpData(6, 0)
    assert OpData(3, 0) * OpData(2, 0) == OpData(6, 0)

    assert (OpData(2, 0.1) * OpData(3, 0.7)).approxeq(OpData(6, 1.43178210632764))
    assert (OpData(3, 0.7) * OpData(2, 0.1)).approxeq(OpData(6, 1.43178210632764))
    assert (OpData(3, 0.1) * OpData(2, 0.7)).approxeq(OpData(6, 2.1095023109729))


def test_division_scalars():
    assert OpData(6, 0) / OpData(2, 0) == OpData(3, 0)
    assert OpData(2, 0) / OpData(4, 0) == OpData(0.5, 0)
    assert OpData(0, 0) / OpData(6, 0) == OpData(0, 0)

    assert OpData(6, 0) / OpData(0, 0) != OpData(0, 0)  # division by zero!
    assert OpData(6, 0) / OpData(0, 0) == OpData(0, 0, dq.DIVZERO)

    assert (OpData(6, 1) / OpData(2, 0.1)).approxeq(OpData(3, 0.522015325445528))


def test_power_scalars():
    assert OpData(6, 0) ** OpData(2, 0) == OpData(36, 0)
    assert OpData(2, 0) ** OpData(1, 0) == OpData(2, 0)
    assert OpData(0, 0) ** OpData(1, 0) == OpData(0, 0)
    assert OpData(2, 0) ** OpData(0.5, 0) == OpData(math.sqrt(2), 0)
    assert (OpData(2, 0) ** OpData(-0.5, 0)).approxeq(OpData(1.0 / math.sqrt(2), 0))
    # complex results are detected and flagged; the result contains just the real component.
    assert (OpData(-2, 0) ** OpData(0.5, 0)).dq == dq.COMPLEX
    assert (OpData(-2, 0) ** OpData(0.5, 0)).n == pytest.approx(0.0)
    assert (OpData(-2, 0) ** OpData(-0.5, 0)).dq == dq.COMPLEX
    assert (OpData(-2, 0) ** OpData(-2, 0)).dq != dq.COMPLEX

    # Zero to -ve power isn't allowed
    assert OpData(0, 0) ** OpData(1, 0) == OpData(0, 0)
    assert OpData(0, 0) ** OpData(0, 0) == OpData(1, 0)
    assert OpData(0, 0) ** OpData(-1, 0) == OpData(0, 0, dq.UNDEF)

    # uncertainty. Dealing with a=0 is complicated.
    assert OpData(0, 2) ** OpData(1, 3) == OpData(0, 2)     # a=0, b=1 : uncertainty is that of a
    assert OpData(0, 2) ** OpData(-1, 3) == OpData(0, 0, dq.UNDEF)    # a=0, b negative : uncertainty 0, undefined
    assert OpData(0, 1) ** OpData(0, 2) == OpData(1, 0)     # otherwise uncertainty 0
    assert OpData(0, 1) ** OpData(2, 2) == OpData(0, 0)     # otherwise uncertainty 0
    assert OpData(0, 1) ** OpData(3, 2) == OpData(0, 0)     # otherwise uncertainty 0


def test_minmax_scalars():
    assert OpData(2, 0) | OpData(3, 0) == OpData(3, 0)
    assert OpData(2, 0) & OpData(3, 0) == OpData(2, 0)

    assert OpData(2, 5) | OpData(3, 6) == OpData(3, 6)
    assert OpData(2, 5) & OpData(3, 6) == OpData(2, 5)


def test_propagation_scalars():
    assert OpData(2, 0) | OpData(3, 0, dq.UNDEF) == OpData(3, 0, dq.UNDEF)
    assert OpData(2, 0) & OpData(3, 0, dq.UNDEF) == OpData(2, 0)

    assert OpData(0, 0, dq.NOUNCERTAINTY) ** OpData(-1, 0) == OpData(0, 0, dq.UNDEF | dq.NOUNCERTAINTY)
    assert OpData(0, 0) ** OpData(-1, 0, dq.NOUNCERTAINTY) == OpData(0, 0, dq.UNDEF | dq.NOUNCERTAINTY)
    assert OpData(2, 0, dq.NOUNCERTAINTY) + OpData(3, 0) == OpData(5, 0, dq.NOUNCERTAINTY)
    assert OpData(2, 0) + OpData(3, 0, dq.NOUNCERTAINTY) == OpData(5, 0, dq.NOUNCERTAINTY)


def test_negate_invert():
    assert -OpData(2, 2) == OpData(-2, 2)
    assert -OpData(-2, 1) == OpData(2, 1)
    assert ~OpData(0.25, 2) == OpData(0.75, 2)
