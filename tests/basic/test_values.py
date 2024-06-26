"""Test the basics principles of the Value type for values with
uncertainty - doesn't test the uncertainty parts themselves, that's
done in uncertainty/test_ops.py.

For binary operations,
each test function is actually a "minisuite" and takes three arguments.
Each of these is a function which generates a value, either a scalar or an array.
Two functions generate the operands, the other generates the result.
Then the main test functions call each of these four times, with combinations of
the different types (scalar and array).

More complex tests are done at the node level in uncertainty/test_ops.py,
but if those tests fail and these pass then there is a likely to be a
problem in the nodes or expression parser."""

import math

import numpy as np
import pytest

from pcot import dq
from pcot.value import Value


def test_expansion_scalar_float():
    """Test expansion of scalar values and optional arguments"""

    # expand a scalar float
    a = Value(0.0)
    assert a.n == 0.0
    assert a.u == 0.0
    assert a.dq == dq.NOUNCERTAINTY


def test_expansion_scalar_int():
    """expand a scalar int, converting to float"""
    a = Value(0)
    assert isinstance(a.n, np.float32)
    assert a.n == 0.0
    assert a.u == 0.0
    assert a.dq == dq.NOUNCERTAINTY


def test_expansion_noUorDQ():
    """expand a nominal array with no uncertainty nor DQ"""
    arr = np.full((4, 4), 1.0, dtype=np.float32)
    a = Value(arr)
    assert a.n.shape == (4, 4)
    assert a.u.shape == (4, 4)
    assert a.dq.shape == (4, 4)
    assert np.allclose(a.n, 1.0)
    assert np.allclose(a.u, 0.0)
    assert np.all(a.dq == dq.NOUNCERTAINTY)


def test_expansion_noDQ():
    """expand a nominal array with a scalar uncertainty"""
    arr = np.full((4, 4), 1.0, dtype=np.float32)
    a = Value(arr, 0.2)
    assert a.n.shape == (4, 4)
    assert a.u.shape == (4, 4)
    assert a.dq.shape == (4, 4)
    assert np.allclose(a.n, 1.0)
    assert np.allclose(a.u, 0.2)
    assert np.all(a.dq == dq.NONE)


def test_expansion_noU():
    """expand a nominal array with a scalar DQ"""
    arr = np.full((4, 4), 1.0, dtype=np.float32)
    a = Value(arr, d=dq.TEST)
    assert a.n.shape == (4, 4)
    assert a.u.shape == (4, 4)
    assert a.dq.shape == (4, 4)
    assert np.allclose(a.n, 1.0)
    assert np.allclose(a.u, 0.0)
    assert np.all(a.dq == dq.TEST | dq.NOUNCERTAINTY)


def test_expansion_scalarUandDQ():
    """expand a nominal array with a scalar uncertainty and DQ"""
    arr = np.full((4, 4), 1.0, dtype=np.float32)
    a = Value(arr, 0.2, dq.UNDEF)
    assert a.n.shape == (4, 4)
    assert a.u.shape == (4, 4)
    assert a.dq.shape == (4, 4)
    assert np.allclose(a.n, 1.0)
    assert np.allclose(a.u, 0.2)
    assert np.all(a.dq == dq.UNDEF)


def test_expansion_invalid():
    """try expanding a scalar N with array U or DQ"""
    with pytest.raises(ValueError):
        Value(0.1, np.full((2, 2), 1.0, dtype=np.float32))

    with pytest.raises(ValueError):
        Value(0.1, d=np.full((2, 2), dq.NONE))


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


def test_addition():
    """Test addition - see notes for this module"""

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
    """Test subtraction - see notes for this module"""

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
    """Test multiplication - see notes for this module"""

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


@pytest.mark.filterwarnings("ignore:divide by zero")
@pytest.mark.filterwarnings("ignore:invalid value")
def test_division():
    """Test division - see notes for this module"""

    def core(a, b, r):
        assert a(6, 0) / b(2, 0) == r(3, 0)
        assert a(2, 0) / b(4, 0) == r(0.5, 0)
        assert a(0, 0) / b(6, 0) == r(0, 0)

        assert a(6, 0) / b(0, 0) != r(0, 0)  # division by zero!
        assert a(6, 0) / b(0, 0) == r(0, 0, dq.DIVZERO)
        assert a(0, 0) / b(0, 0) == r(0, 0, dq.UNDEF | dq.DIVZERO)

        assert (a(6, 1) / b(2, 0.1)).approxeq(r(3, 0.522015325445528))

    core(Value, Value, Value)
    core(genArray, genArray, genArray)
    core(Value, genArray, genArray)
    core(genArray, Value, genArray)


@pytest.mark.filterwarnings("ignore:divide by zero")
@pytest.mark.filterwarnings("ignore:invalid value")
def test_power():
    """Test exponentiation - see notes for this module"""

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
    """Test min and max - see notes for this module at the top of this file"""

    def core(a, b, r):
        assert a(2, 0) | b(3, 0) == r(3, 0)
        assert a(2, 0) & b(3, 0) == r(2, 0)
        assert a(2, 5) | b(3, 6) == r(3, 6)
        assert a(2, 5) & b(3, 6) == r(2, 5)

    core(Value, Value, Value)
    core(genArray, genArray, genArray)
    core(Value, genArray, genArray)
    core(genArray, Value, genArray)


@pytest.mark.filterwarnings("ignore:divide by zero")
def test_propagation():
    """Test DQ propagation - see notes for this module"""

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


def test_propagation_unary():
    """test that unary operators copy their DQ bits to the result"""

    def core(a):
        assert -a(2, 0.1) == a(-2, 0.1, dq.NONE)
        assert ~a(0.25, 0.1) == a(0.75, 0.1, dq.NONE)
        assert -a(2, 0.1, dq.TEST) == a(-2, 0.1, dq.TEST)
        assert ~a(0.25, 0.1, dq.TEST) == a(0.75, 0.1, dq.TEST)

    core(Value)
    core(genArray)


def test_negate_invert():
    """Test unary operations"""

    def core(a):
        assert -a(2, 2) == a(-2, 2)
        assert -a(-2, 1) == a(2, 1)
        assert ~a(0.25, 2) == a(0.75, 2)

    core(Value)
    core(genArray)

