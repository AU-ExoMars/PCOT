"""Dealing with numbers and uncertainties
   Don't add any PCOT bits into this code, because it gets 
   tested from elsewhere.
"""

# First, methods to perform the operations. These are separate from Number so we can use them on numpy data too.
import numpy as np


class Number:
    def __init__(self, n, u=0.0):
        self.n = float(n)
        self.u = float(u)

    def copy(self):
        return Number(self.n, self.u)

    def serialise(self):
        return self.n, self.u

    @staticmethod
    def deserialise(t):
        n, u = t
        return Number(n, u)

    def __add__(self, other):
        return Number(self.n + other.n, add_sub_unc(self.u, other.u))

    def __sub__(self, other):
        return Number(self.n - other.n, add_sub_unc(self.u, other.u))

    def __mul__(self, other):
        return Number(self.n * other.n, mul_unc(self.n, self.u, other.n, other.u))

    def __truediv__(self, other):
        return Number(self.n / other.n, div_unc(self.n, self.u, other.n, other.u))

    def __pow__(self, power, modulo=None):
        if self.n == 0.0 and power.n < 0:
            return Number(0, 0)  # zero cannot be raised to -ve power so invalid, but we use zero as a dummy.
        return Number(self.n ** power.n, pow_unc(self.n, self.u, power.n, power.u))

    def __and__(self, other):
        """The & operator actually finds the minimum (Zadeh op)"""
        if self.n > other.n:
            return other.copy()
        else:
            return self.copy()

    def __or__(self, other):
        """The & operator actually finds the maximum (Zadeh op)"""
        if self.n < other.n:
            return other.copy()
        else:
            return self.copy()

    def __neg__(self):
        return Number(-self.n, self.u)

    def __invert__(self):
        return Number(1-self.n, self.u)

    def __str__(self):
        return str(f"{self.n} ± {self.u}")
