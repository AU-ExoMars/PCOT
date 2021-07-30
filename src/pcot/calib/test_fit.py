from unittest import TestCase
from . import fit

# generate test data
import numpy as np


def gen(m, c):
    rho = [0.2, 0.4, 0.5, 0.6, 0.8]  # one value for each patch

    signal = []
    for x in rho:
        # this is the basic relationship we are trying to recover
        y = m * x + c
        y = list(y + np.random.randn(1000) * 0.01)  # multiple values for each patch
        signal.append(y)
    return rho, signal


class Test(TestCase):
    def test_fit(self):
        for m in [1, 2, 3, 4, 5]:
            for n in range(10):
                rho, signal = gen(m, 10)
                M, C, SDM, SDC = fit(rho, signal)
                ratio = M/m
                print("m={} outm={}, ratio={}, c={}, sdm={}, sdc={}".format(m, M, M / m, C, SDM, SDC))
                self.assertTrue(abs(ratio-1) < 0.01)
                self.assertTrue(abs(C-10) < 0.01)
                self.assertTrue(SDM < 0.05)
                self.assertTrue(SDC < 0.05)
