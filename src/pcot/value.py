import numpy as np

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

    def __init__(self, n, u=None, d=dq.NONE):
        """Initialise a value - either array of float32 or scalar.
        n = nominal value
        u = uncertainty (SD)
        d = data quality bits (see DQ; these are error bits).
        This has to make sure that n, u and d are all the same dimensionality."""

        # python doesn't do common subexpression elimination, apparently..
        usc = np.isscalar(u)
        dsc = np.isscalar(d)

        if np.isscalar(n):
            if not usc or not dsc:
                raise Exception("Value nominal, uncertainty, and DQ bits must be either all scalar or all array")
        elif dsc:
            # data is not scalar, but no reasonable DQ is provided - make one.
            d = np.full(n.shape, d)
        elif usc or dsc:
            raise Exception("Value nominal, uncertainty, and DQ bits must be either all scalar or all array")
        elif n.shape != u.shape or n.shape != d.shape:
            raise Exception("Value nominal, uncertainty, and DQ bits must be the same shape")

        self.n = n  # nominal, either float or ndarray
        self.u = u  # uncertainty, either float or ndarray
        self.dq = d  # if a result, the DQ bits. May be zero, shouldn't be None.


    def copy(self):
        return Value(self.n, self.u, self.dq)

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
            n = np.where((self.n == 0.0) & (power.n < 0), 0, self.n ** power.n)
            u = np.where((self.n == 0.0) & (power.n < 0), 0, pow_unc(self.n, self.u, power.n, power.u))
            d = combineDQs(self, power, np.where((self.n == 0.0) & (power.n < 0), dq.UNDEF, dq.NONE))
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

    def __neg__(self):
        return Value(-self.n, self.u, self.dq)

    def __invert__(self):
        return Value(1 - self.n, self.u, self.dq)

    def __str__(self):
        if np.isscalar(self.n):
            names = dq.names(self.dq)
            return f"Value:{self.n}±{self.u}{names}"
        else:
            return f"Value:array{self.n.shape}"

    def __repr__(self):
        return self.__str__()
