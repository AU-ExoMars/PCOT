"""
Test binary operations on vector values (including vector/scalar and scalar/vector)

Actually, this stuff is all tested in basic/test_values.py, so we don't need to do it here. But we will add a
"sanity check" where heterogenous arrays are tested (i.e. not all the same value)

These tests work by splitting the values into scalars and then performing the operation on each scalar - so
the ground truth also comes from Value code. This is OK because these are tested elsewhere.

"""
from typing import Any, Callable

import numpy as np
import pytest

from pcot import dq
from pcot.value import Value

# one vector
va = Value([1, 2, 3], [0.1, 0.2, 0.3], [dq.TEST, dq.NONE, dq.ERROR])
# another vector, different values
vb = Value([2, 3, 4], [0.2, 0.3, 0.4], [dq.NONE, dq.UNDEF, dq.ERROR])
# a scalar again different
sa = Value(5, 0.5, dq.DIVZERO)
# another scalar, different
sb = Value(6, 0.6, dq.COMPLEX)


def calc(a: Value, b: Value, op: Callable[[Value, Value], Value]) -> Value:
    """Calculate a binary operation on two values, returning the result. This works by splitting the value
    out into elements, so we're only doing scalar operations, and "upgrading" incoming scalars to vectors first.
    It's how we get ground truth for the tests."""

    def convert_to_vector(v: Value, shape_v: Value) -> Value:
        """Convert v (a scalar) to a vector the same shape as shape_v"""
        nn = np.full_like(shape_v.n, v.n)
        uu = np.full_like(shape_v.u, v.u)
        dd = np.full_like(shape_v.dq, v.dq)
        return Value(nn, uu, dd)

    # if a is a scalar and b is a vector, make it a vector the same size as b
    if np.isscalar(a.n) and not np.isscalar(b.n):
        a = convert_to_vector(a, b)
    # same with b
    elif np.isscalar(b.n) and not np.isscalar(a.n):
        b = convert_to_vector(b, a)

    # should now be either both scalar or both vector of the same shape
    assert np.isscalar(a.n) == np.isscalar(b.n)
    if np.isscalar(a.n):
        # easy case, two scalars
        return op(a, b)
    else:
        assert a.n.shape == b.n.shape

        # having done all that, split into single scalars!
        alist = a.split()
        blist = b.split()

        # perform the operation on all the values in the vectors
        res = [op(a,b) for a,b in zip(alist, blist)]
        # turn the results into numpy arrays that can be passed to a value constructor
        n = np.array([r.n for r in res]).reshape(a.n.shape)
        u = np.array([r.u for r in res]).reshape(a.n.shape)
        d = np.array([r.dq for r in res]).reshape(a.n.shape)
        return Value(n, u, d)

ops = [
    ("addition", lambda a, b: a + b),
    ("subtraction", lambda a, b: a - b),
    ("multiplication", lambda a, b: a * b),
    ("division", lambda a, b: a / b),
    ("power", lambda a, b: a ** b)
]

@pytest.mark.parametrize("t", ops, ids=lambda x: x[0])
def test_binops_ss(t):
    name, op = t
    r = calc(sa, sb, op)
    assert r.approxeq(op(sa, sb))

@pytest.mark.parametrize("t", ops, ids=lambda x: x[0])
def test_binops_sv(t):
    name, op = t
    r = calc(sa, vb, op)
    assert r.approxeq(op(sa, vb))

@pytest.mark.parametrize("t", ops, ids=lambda x: x[0])
def test_binops_vs(t):
    name, op = t
    r = calc(va, sb, op)
    assert r.approxeq(op(va, sb))


@pytest.mark.parametrize("t", ops, ids=lambda x: x[0])
def test_binops_vv(t):
    name, op = t
    r = calc(va, vb, op)
    assert r.approxeq(op(va, vb))


