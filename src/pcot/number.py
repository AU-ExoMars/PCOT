"""Dealing with numbers and uncertainties"""

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
    """Exponentiation. This is horrible because there are special cases. I'm going to arrange it so that
    you can only meaningfully do it on a non-negative base."""

    # This is clever. If a=0 we should
    #       if b=1:     output UA
    #       if b<0:     output 100
    #       otherwise:  output 0

    a = np.abs(a)                       # no negative base allowed!
    if np.any(a == 0):                  # zero is a special case, deal with those
        result = np.zeros_like(a)       # get an array of zeros
        result[b == 1] = ua[b == 1]     # set those places where b=1 to ua.
        result[b < 0] = 100             # set those places where b<0 to 100.
        return result

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
