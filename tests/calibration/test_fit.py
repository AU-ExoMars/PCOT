"""Tests of the basic calibration line-fitting technique"""

from pcot.calib import fit

import numpy as np


def generate_test_data(m, c):
    """Generate some test data. This consists of a tuple of the form [rho, signal].
    The rho list is a set of putative patch intensities.
    The signal is a set of lists - one for each patch - containing a bunch of data read from that patch.
    As such, in this test, the signal consists of a bunch of random values for each rho (patch), but there is
    a linear relationship such that mean(signal for rho) = m*rho + c.
    Does that make sense?

    So the output is a list of patch intensities, and a set of signals for each patch. We are trying to recover
    the linear between the patch intensity and the mean signal."""

    rho = [0.2, 0.4, 0.5, 0.6, 0.8]  # one value for each patch

    signal = []
    for x in rho:
        # this is the basic relationship we are trying to recover
        y = m * x + c
        y = list(y + np.random.randn(1000) * 0.01)  # multiple values for each patch
        signal.append(y)
    return rho, signal


def test_fit():
    """Perform some basic tests - we generate some data around a known slope and intercept, and check
    we recover that slope and intercept correctly"""
    for m in [1, 2, 3, 4, 5]:               # test at different slopes
        for c in range(-10, 10):                 # and different intensities
            rho, signal = generate_test_data(m, c)     # generate test data for that slope and intensity
            M, C, SDM, SDC = fit(rho, signal)           # recover M, C and their stddevs
            ratio = M/m                                 # how wrong is the slope?
            # print("m={} outm={}, ratio={}, c={}, sdm={}, sdc={}".format(m, M, M / m, C, SDM, SDC))
            assert abs(ratio-1) < 0.01      # make sure the slope isn't too wrong
            assert abs(C-c) < 0.01          # and that the intercept is good
            assert SDM < 0.05               # and that the stddevs are small.
            assert SDC < 0.05
