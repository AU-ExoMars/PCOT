import math

import numpy as np
import pytest

from pcot import dq
from pcot.value import Value


def genArray(n, u, d=dq.NONE):
    """generate an array filled with the appropriate values"""
    n = np.full((5, 5), n, dtype=np.float32)
    u = np.full(n.shape, u, dtype=np.float32)
    d = np.full(n.shape, d, dtype=np.uint16)
    return Value(n, u, d)


def test_approx():
    """Test the "approximately equal" function for both scalars and arrays"""

    def core(a):
        assert a(0, 0).approxeq(a(0, 0))
        assert a(1, 0).approxeq(a(1, 0))
        assert not a(0, 0).approxeq(a(0, 0, dq.UNDEF))
        assert not a(1, 0).approxeq(a(0, 0))
        assert not a(0, 1).approxeq(a(0, 0))
        assert not a(0, 0).approxeq(a(1, 0))
        assert not a(0, 0).approxeq(a(0, 1))
        assert not a(0, 0.00001).approxeq(a(0, 0))

    core(Value)
    core(genArray)


def test_equality():
    """Test the equality operator"""

    def core(a):
        assert a(0, 0) == a(0, 0)
        assert a(0, 0) != a(1, 0)
        assert a(1, 0) != a(0, 0)
        assert a(0, 0) != a(0, 1)
        assert a(0, 1) != a(0, 0)
        assert a(0, 0, dq.UNDEF) != a(0, 0)
        assert a(0, 0) != a(0, 0, dq.UNDEF)
        assert a(0, 0, dq.BAD) != a(0, 0, dq.UNDEF)
        assert a(0, 0) == a(0, 0)

    core(Value)
    core(genArray)

    assert Value(0, 0) != genArray(0, 0)


# each test function is actually a "minisuite" and takes three arguments.
# Each of these is a function which generates a value, either a scalar or an array.
# Two functions generate the operands, the other generates the result.
# Then the main test functions call each of these four times, with combinations of
# the different types (scalar and array).


def test_addition():
    def core(a, b, r):
        assert a(2, 0) + b(3, 0) == r(5, 0)
        assert a(3, 0) + b(3, 0) != r(5, 0)
        assert a(2, 3) + b(7, 4) == r(9, 5)
        assert a(2, 4) + b(7, 3) == r(9, 5)

    core(Value, Value, Value)
    core(genArray, genArray, genArray)
    core(Value, genArray, genArray)
    core(genArray, Value, genArray)


def test_subtraction():
    def core(a, b, r):
        assert a(2, 0) - b(3, 0) == r(-1, 0)
        assert a(3, 0) - b(2, 0) == r(1, 0)
        assert a(2, 3) - b(7, 4) == r(-5, 5)
        assert a(2, 4) - b(7, 3) == r(-5, 5)

    core(Value, Value, Value)
    core(genArray, genArray, genArray)
    core(Value, genArray, genArray)
    core(genArray, Value, genArray)


def test_multiplication():
    def core(a, b, r):
        assert a(2, 0) * b(3, 0) == r(6, 0)
        assert a(3, 0) * b(2, 0) == r(6, 0)

        assert (a(2, 0.1) * b(3, 0.7)).approxeq(r(6, 1.43178210632764))
        assert (a(3, 0.7) * b(2, 0.1)).approxeq(r(6, 1.43178210632764))
        assert (a(3, 0.1) * b(2, 0.7)).approxeq(r(6, 2.1095023109729))

    core(Value, Value, Value)
    core(genArray, genArray, genArray)
    core(Value, genArray, genArray)
    core(genArray, Value, genArray)


def test_division():
    def core(a, b, r):
        assert a(6, 0) / b(2, 0) == r(3, 0)
        assert a(2, 0) / b(4, 0) == r(0.5, 0)
        assert a(0, 0) / b(6, 0) == r(0, 0)

        assert a(6, 0) / b(0, 0) != r(0, 0)  # division by zero!
        assert a(6, 0) / b(0, 0) == r(0, 0, dq.DIVZERO)

        assert (a(6, 1) / b(2, 0.1)).approxeq(r(3, 0.522015325445528))

    core(Value, Value, Value)
    core(genArray, genArray, genArray)
    core(Value, genArray, genArray)
    core(genArray, Value, genArray)


def test_power():
    def core(a, b, r):
        assert a(6, 0) ** b(2, 0) == r(36, 0)
        assert a(2, 0) ** b(1, 0) == r(2, 0)
        assert a(0, 0) ** b(1, 0) == r(0, 0)
        assert a(2, 0) ** b(0.5, 0) == r(math.sqrt(2), 0)
        assert (a(2, 0) ** b(-0.5, 0)).approxeq(r(1.0 / math.sqrt(2), 0))
        # complex results are detected and flagged; the result contains just the real component.

        assert (a(-2, 0) ** b(0.5, 0)).approxeq(r(0, 0, dq.COMPLEX))
        assert not (a(-2, 0) ** b(0.5, 0)).approxeq(r(0, 0))  # can't do this.
        assert (a(-2, 0) ** b(-0.5, 0)).approxeq(r(0, 0, dq.COMPLEX))
        assert (a(-2, 0) ** b(-2, 0)).approxeq(r(0.25, 0))  # but this is file

        # Zero to -ve power isn't allowed
        assert a(0, 0) ** b(1, 0) == r(0, 0)
        assert a(0, 0) ** b(0, 0) == r(1, 0)
        assert a(0, 0) ** b(-1, 0) == r(0, 0, dq.UNDEF)

        # uncertainty. Dealing with a=0 is complicated.
        assert a(0, 2) ** b(1, 3) == r(0, 2)  # a=0, b=1 : uncertainty is that of a
        assert a(0, 2) ** b(-1, 3) == r(0, 0, dq.UNDEF)  # a=0, b negative : uncertainty 0, undefined
        assert a(0, 1) ** b(0, 2) == r(1, 0)  # otherwise uncertainty 0
        assert a(0, 1) ** b(2, 2) == r(0, 0)  # otherwise uncertainty 0
        assert a(0, 1) ** b(3, 2) == r(0, 0)  # otherwise uncertainty 0

        # "ordinary" uncertainties
        assert (a(2, 0.3) ** b(3, 0.2)).approxeq(r(8, 3.76695629329975))
        assert (a(2, 0.2) ** b(3, 0.3)).approxeq(r(8, 2.92017283053056))

    core(Value, Value, Value)
    core(genArray, genArray, genArray)
    core(Value, genArray, genArray)
    core(genArray, Value, genArray)


def test_minmax():
    def core(a, b, r):
        assert a(2, 0) | b(3, 0) == r(3, 0)
        assert a(2, 0) & b(3, 0) == r(2, 0)
        assert a(2, 5) | b(3, 6) == r(3, 6)
        assert a(2, 5) & b(3, 6) == r(2, 5)
    core(Value, Value, Value)
    core(genArray, genArray, genArray)
    core(Value, genArray, genArray)
    core(genArray, Value, genArray)


def test_propagation():
    def core(a, b, r):
        assert a(2, 0) | b(3, 0, dq.UNDEF) == r(3, 0, dq.UNDEF)
        assert a(2, 0) & b(3, 0, dq.UNDEF) == r(2, 0)

        assert a(0, 0, dq.NOUNCERTAINTY) ** b(-1, 0) == r(0, 0, dq.UNDEF | dq.NOUNCERTAINTY)
        assert a(0, 0) ** b(-1, 0, dq.NOUNCERTAINTY) == r(0, 0, dq.UNDEF | dq.NOUNCERTAINTY)
        assert a(2, 0, dq.NOUNCERTAINTY) + b(3, 0) == r(5, 0, dq.NOUNCERTAINTY)
        assert a(2, 0) + b(3, 0, dq.NOUNCERTAINTY) == r(5, 0, dq.NOUNCERTAINTY)
    core(Value, Value, Value)
    core(genArray, genArray, genArray)
    core(Value, genArray, genArray)
    core(genArray, Value, genArray)


def test_negate_invert():
    def core(a):
        assert -a(2, 2) == a(-2, 2)
        assert -a(-2, 1) == a(2, 1)
        assert ~a(0.25, 2) == a(0.75, 2)
    core(Value)
    core(genArray)
