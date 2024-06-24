import math
from typing import Any, Union

import numpy as np
from numpy.typing import NDArray

from pcot import dq


def add_sub_unc(ua, ub):
    """For addition and subtraction, errors add in quadrature"""
    return np.sqrt(ua ** 2 + ub ** 2)


def add_sub_unc_list(lst):
    """Add a whole list of uncertainties"""
    return np.sqrt(np.sum(lst ** 2))


def mul_unc(a, ua, b, ub):
    """Multiplication - this is derived from the standard answer
    (thanks, Wolfram!) assuming the values are real"""
    # This is the "standard answer" - you can confirm it's the same when all values are positive
    #    return np.abs(a*b) * np.sqrt((ua/a)**2 + (ub/b)**2)

    # this is the simplification
    return np.sqrt((a * ub) ** 2 + (b * ua) ** 2)


def div_unc(a, ua, b, ub):
    """Division. Also derived from the standard answer.
    """
    #   standard answer - throws exceptions with either a or b is 0.
    # return np.abs(a/b) * np.sqrt((ua/a)**2 + (ub/b)**2)

    #   is equivalent to this when all values are positive
    return np.sqrt(((a * ub) ** 2 + (b * ua) ** 2)) / (b ** 2)


def powcore(a, ua, b, ub):
    """Core function for exponentiation uncertainty once values have
    been cleaned"""
    # This is the canonical version, which is much slower.
    # x = (a**(b-1)*b*ua)**2
    # y = (a**b*(np.log(a))*ub)**2
    # return np.sqrt(x + y)

    # and this is the simplified version.
    x = a ** (2 * b - 2)
    y = (a * ub * np.log(a)) ** 2 + (b * ua) ** 2
    return np.sqrt(x * y)


def pow_unc(a, ua, b, ub):
    """Exponentiation. This is horrible because there are special cases when a==0"""

    ascal = np.isscalar(a)
    bscal = np.isscalar(b)

    # If a=0 we should
    #       if b=1:     output UA
    #       if b<0:     output 0 (INVALID)
    #       otherwise:  output 0
    # The standard calculation performed by the uncertainties module uses the absolute
    # value of a. I'm not sure this is correct, but I'll do it anyway.

    if ascal and bscal:
        if a == 0:
            if b == 1:
                return ua
            elif b < 0:
                return 0  # these two cases are the same, but it reality the <0 case is invalid.
            else:
                return 0
        # if a!=0 we drop through to the main calculation, after absing a
        a = abs(a)
    elif ascal:
        # a is scalar, b is an array
        if a == 0:
            result = np.zeros_like(b)
            result[b == 1] = ua  # see below for what we're doing here
            result[b < 0] = 0
            return result
        # drop through to main calculation again
        a = abs(a)
    else:
        # a is an array, b is a scalar or an array
        # for now, just turn b into an array if it isn't one
        if bscal:
            b = np.full_like(a, b)

        a = np.abs(a)  # this isn't ideal!
        if np.any(a == 0):
            # first, work out where a is 0
            zeros = a == 0
            # set those values in a to be 1 for now.
            a[zeros] = 1
            # Perform the core calculation
            result = powcore(a, ua, b, ub)
            # set the "zeros" back to zero
            result[zeros] = 0
            # set to ua where b is 1 and zeros is true
            np.putmask(result, np.logical_and(zeros, b == 1), ua)
            return result

    # the default calculation
    return powcore(a, ua, b, ub)


def combineDQs(a, b, extra=None):
    """Bitwise OR DQs together. A and B are the DQs of the two data we're combining, which the result
    should inherit. Extra is any extra bits that need to be set."""
    if a.dq is None:
        r = b.dq
    elif b.dq is None:
        r = a.dq
    else:
        r = a.dq | b.dq

    # if r is a zero-dimensional array, convert it

    if extra is not None:
        # first, extra *could* be a 0-dimensional array because of how np.where works on scalar inputs
        if extra.shape == ():
            extra = int(extra)
        else:
            # if it isn't, it could well be the wrong integer type - so convert it to the correct one.
            extra = extra.astype(np.uint16)
        if r is None:
            r = extra
        else:
            r |= extra

    return r


def reduce_if_zero_dim(n):
    if not np.isscalar(n):
        n = n[()]
    return n


EPSILON = 0.00001


class Value:
    """Wraps a value with uncertainty and data quality. This can be either an array or a scalar, but they
    have to match."""

    # each of these is either a scalar or an array
    n: Union[NDArray[np.float32], np.float32]
    u: Union[NDArray[np.float32], np.float32]
    dq: Union[NDArray[np.uint16], np.uint16]

    def __init__(self, n, u: Any = 0.0, d=dq.NONE):
        """Initialise a value - either array of float32 or scalar.
        n = nominal value
        u = uncertainty (SD)
        d = data quality bits (see DQ; these are error bits).
        This has to make sure that n, u and d are all the same dimensionality."""

        n = np.float32(n)  # convert to correct types (will also convert arrays)
        u = np.float32(u)
        d = np.uint16(d)

        if np.isscalar(n):
            # if N is scalar, U and D must be scalar.
            if not np.isscalar(u) or not np.isscalar(d):
                raise ValueError("Value nominal, uncertainty, and DQ bits must be either all scalar or all array")
        else:
            # N is an array. If U or DQ are scalar, convert to arrays of the same shape
            if np.isscalar(u):
                u = np.full(n.shape, u, dtype=np.float32)
            if np.isscalar(d):
                d = np.full(n.shape, d, dtype=np.uint16)

            # check all arrays are same shape
            if n.shape != u.shape or n.shape != d.shape:
                raise ValueError("Value nominal, uncertainty, and DQ bits must be the same shape")

        self.n = n  # nominal, either float or ndarray
        self.u = u  # uncertainty, either float or ndarray
        self.dq = d  # if a result, the DQ bits. May be zero, shouldn't be None.

    def copy(self, deep=True):
        """Produce a deep copy if "deep" is true (and it's an array), otherwise the copy will be shallow"""
        if deep and not np.isscalar(self.n):
            return Value(np.copy(self.n), np.copy(self.u), np.copy(self.dq))
        return Value(self.n, self.u, self.dq)

    def isscalar(self):
        return np.isscalar(self.n)

    def serialise(self):
        return self.n, self.u, self.dq

    @staticmethod
    def deserialise(t):
        n, u, d = t
        return Value(n, u, d)

    def __eq__(self, other):
        return np.array_equal(self.n, other.n) and np.array_equal(self.u, other.u) and np.array_equal(self.dq, other.dq)

    def approxeq(self, other):  # used in tests
        return np.allclose(self.n, other.n) and np.allclose(self.u, other.u) and np.array_equal(self.dq, other.dq)

    def __add__(self, other):
        return Value(self.n + other.n, add_sub_unc(self.u, other.u),
                     combineDQs(self, other))

    def __sub__(self, other):
        return Value(self.n - other.n, add_sub_unc(self.u, other.u),
                     combineDQs(self, other))

    def __mul__(self, other):
        return Value(self.n * other.n, mul_unc(self.n, self.u, other.n, other.u),
                     combineDQs(self, other))

    def __truediv__(self, other):
        try:
            n = np.where(other.n == 0, 0, self.n / other.n)
            u = np.where(other.n == 0, 0, div_unc(self.n, self.u, other.n, other.u))

            extra = np.where(other.n == 0, dq.DIVZERO, dq.NONE) | \
                    np.where((other.n == 0) & (self.n == 0), dq.UNDEF, dq.NONE)

            d = combineDQs(self, other, extra)
            # fold zero dimensional arrays (from np.where) back into scalars
            n = reduce_if_zero_dim(n)
            u = reduce_if_zero_dim(u)
            d = reduce_if_zero_dim(d)
        except ZeroDivisionError:
            # should only happen where we're dividing scalars
            n = 0
            u = 0
            if self.n == 0:
                d = self.dq | other.dq | dq.DIVZERO | dq.UNDEF
            else:
                d = self.dq | other.dq | dq.DIVZERO

        return Value(n, u, d)

    def __pow__(self, power, modulo=None):
        # zero cannot be raised to -ve power so invalid, but we use zero as a dummy.
        try:
            # It seems that when you perform an operation on a masked array that results in a nan.
            # it puts the fill value for the array into the data and masks it! Therefore we have to make
            # sure any masked arrays which feed into here are masked appropriately.
            undefined = (self.n == 0.0) & (power.n < 0)
            n = np.where(undefined, 0, self.n ** power.n)
            u = np.where(undefined, 0, pow_unc(self.n, self.u, power.n, power.u))
            d = combineDQs(self, power, np.where(undefined, dq.UNDEF, dq.NONE))
            # remove NaN in n and u, and replace with zero, marking the n NaNs in the DQ
            d |= np.where(np.isnan(n), dq.COMPLEX, dq.NONE)
            n[np.isnan(n)] = 0
            u[np.isnan(u)] = 0
            # remove imaginary component of complex result but mark as complex in DQ
            d |= np.where(n.imag != 0.0, dq.COMPLEX, dq.NONE)
            n = n.real
            # and fold zerodim arrays back to scalar
            n = reduce_if_zero_dim(n)
            u = reduce_if_zero_dim(u)
            d = reduce_if_zero_dim(d)
        except ZeroDivisionError:
            # should only happen where we're processing scalars
            n = 0
            u = 0
            d = self.dq | power.dq | dq.UNDEF
        return Value(n, u, d)

    def __and__(self, other):
        """The & operator actually finds the minimum (Zadeh fuzzy op)"""
        n = np.where(self.n > other.n, other.n, self.n)
        u = np.where(self.n > other.n, other.u, self.u)
        d = np.where(self.n > other.n, other.dq, self.dq)
        return Value(n, u, d)

    def __or__(self, other):
        """The | operator actually finds the maximum (Zadeh fuzzy op)"""
        n = np.where(self.n < other.n, other.n, self.n)
        u = np.where(self.n < other.n, other.u, self.u)
        d = np.where(self.n < other.n, other.dq, self.dq)
        return Value(n, u, d)

    def sqrt(self):
        """This is probably simpler but might be slightly slower"""
        return self ** Value(0.5, 0, dq.NONE)

    def sin(self):
        return Value(np.sin(self.n),
                     np.sqrt((np.cos(self.n) * self.u) ** 2),
                     self.dq)

    def cos(self):
        return Value(np.cos(self.n),
                     np.sqrt((np.sin(self.n) * self.u) ** 2),
                     self.dq)

    def tan(self):
        # Now you might think this would work:
        #   return self.sin()/self.cos()
        # but it doesn't because they clearly aren't independent. Instead
        # we calculate from the secant (although that gets Fun when zeroes are involved)

        # we avoid division by zero and we do the same calc differently
        # for scalar and array. It's really unlikely that the zero case will
        # come up, but still.

        # values with a cosine of less than this amoung will be replaced with
        # COSREPLACE and have the DIVZERO bit set in the result
        COSTHRESH = 1e-7
        COSREPLACE = 1e-7

        extra = dq.NONE  # bits to OR into the DQ of the result
        if self.isscalar():
            cos = np.cos(self.n)
            if np.abs(cos) < COSTHRESH:
                cos = COSREPLACE
                extra = dq.DIVZERO
            sec = 1.0 / cos
            u = np.sqrt((sec ** 2 * self.u) ** 2)
        else:
            cos = np.cos(self.n)
            cossmall = np.abs(cos) < COSTHRESH
            cos = np.where(cossmall, COSREPLACE, cos)  # turn infs into large
            extra = np.where(cossmall, dq.DIVZERO, dq.NONE)
            sec = 1.0 / cos
            u = np.sqrt((sec ** 2 * self.u) ** 2)

        return Value(np.tan(self.n), u, self.dq | extra)

    def __abs__(self):
        return Value(np.abs(self.n), self.u, self.dq)

    def __neg__(self):
        return Value(-self.n, self.u, self.dq)

    def __invert__(self):
        return Value(1 - self.n, self.u, self.dq)

    def __str__(self):
        return self.sigfigs(5)

    @staticmethod
    def scalar_out(n, u, d, sigfigs=5):
        """Output a scalar value"""
        # first get a string for the DQ bits
        dqstr = dq.chars(d)
        return f"{n:.{sigfigs}g}±{u:.{sigfigs}g}{dqstr}"

    def sigfigs(self, figs):
        """a string representation to a given number of significant figures"""
        if np.isscalar(self.n):
            return self.scalar_out(self.n, self.u, self.dq, figs)
        else:
            if len(self.n.shape) == 1 and self.n.shape[0] < 20:
                # print 1D arrays if they are short enough
                return "[" + ", ".join([self.scalar_out(n, u, d, figs) for n, u, d in
                                        zip(self.n, self.u, self.dq)]) + "]"
            else:
                return f"Value:array{self.n.shape}"

    def __repr__(self):
        return self.__str__()

    def brief(self):
        """Very brief ASCII-safe representation used in e.g. test names"""
        if self.dq != 0:
            return f"{self.n}|{self.u}|{dq.names(self.dq, True)}"
        else:
            return f"{self.n}|{self.u}"
