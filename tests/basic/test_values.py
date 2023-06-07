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
    assert OpData(0, 0) / OpData(6, 0) == OpData(0, 0)
    assert OpData(6, 0) / OpData(0, 0) != OpData(0, 0)
    assert OpData(6, 0) / OpData(0, 0) == OpData(0, 0, dq.DIVZERO)

    assert (OpData(6, 1) / OpData(2, 0.1)).approxeq(OpData(3, 0.522015325445528))
