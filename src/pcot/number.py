"""Dealing with numbers and uncertainties
   Don't add any PCOT bits into this code, because it gets 
   tested from elsewhere.
"""

# First, methods to perform the operations. These are separate from Number so we can use them on numpy data too.
import numpy as np
from numpy import sqrt


def add_sub_unc(ua, ub):
    """For addition and subtraction, errors add in quadrature"""
    return np.sqrt(ua**2 + ub**2)


def mul_unc(a, ua, b, ub):
    """Multiplication - this is Goodman's formula"""
    return np.sqrt((a*ub)**2 + (b*ua)**2)


def div_unc(a, ua, b, ub):
    """Division. This is a bit of a weird one; I used an online analytical calculator to obtain it
    https://astro.subhashbose.com/tools/error-propagation-calculator
    and had a chat with ChatGPT although that was a bit of a walk up the garden path (it was hopeless).
    It does, however, match the values given by the uncertainties package when under test.
    """
    return np.sqrt(((a*ub)**2 + (b*ua)**2)/(b**4))


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
        if a==0:
            if b==1:
                return ua
            elif b<0:
                return 0  # these two cases are the same, but it reality the <0 case is invalid.
            else:
                return 0
        # if a!=0 we drop through to the main calculation, after absing a
        a=abs(a)
    elif ascal:
        # a is scalar, b is an array
        if a==0:
            result = np.zeros_like(b)
            result[b==1] = ua           # see below for what we're doing here
            result[b<0] = 0
            return result
        # drop through to main calculation again
        a=abs(a)
    else:
        # a is an array, b is a scalar or an array
        # for now, just turn b into an array if it isn't one
        if bscal:
            b = np.full_like(a,b)
        
        a = np.abs(a)   # this isn't ideal!
        if np.any(a==0):
            # first, work out where a is 0
            zeros = a==0
            # set those values in a to be 1 for now.
            a[zeros]=1
            # Perform the core calculation
            x = a ** (2 * b - 2)
            y = (a * ub * np.log(a)) ** 2 + (b * ua) ** 2
            result = np.sqrt(x * y)
            # set the "zeros" back to zero
            result[zeros]=0
            # set to ua where b is 1 and zeros is true
            np.putmask(result,np.logical_and(zeros,b==1),ua)
            return result

    # the default calculation
    x = a ** (2 * b - 2)
    y = (a * ub * np.log(a)) ** 2 + (b * ua) ** 2
    return np.sqrt(x * y)


class Number:
    def __init__(self, n, u=0.0):
        self.n = float(n)
        self.u = float(u)

    def __add__(self, other):
        return Number(self.n+other.n, add_sub_unc(self.u, other.u))

    def __sub__(self, other):
        return Number(self.n-other.n, add_sub_unc(self.u, other.u))

    def __mul__(self, other):
        return Number(self.n*other.n, mul_unc(self.n, self.u, other.n, other.u))

    def __truediv__(self, other):
        return Number(self.n*other.n, div_unc(self.n, self.u, other.n, other.u))

    def __pow__(self, power, modulo=None):
        return Number(self.n**power.n, div_unc(self.n, self.u, power.n, power.u))

    def __str__(self):
        return str(self.n)
