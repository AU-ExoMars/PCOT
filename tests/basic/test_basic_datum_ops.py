""""
Test ordering of datum binops.

These are very basic tests on subtraction to ensure that __rsub__ is doing the right thing (and by extension
the other __r...__ dunders).
"""
import numpy as np

from fixtures import genrgb
from pcot import dq
from pcot.datum import Datum
from pcot.value import Value


def test_sub_add_datum():
    d = Datum.k(4) - Datum.k(2)
    assert d.get(Datum.NUMBER).n == 2.0

    d = Datum.k(4) - 2
    assert d.get(Datum.NUMBER).n == 2.0

    d = 4 - Datum.k(2)
    assert d.get(Datum.NUMBER).n == 2.0


def test_guppy_example():
    myImageCube = genrgb(32, 32,
                  1.1, 2.2, 3.3,  # rgb
                  u=(0.1, 0.2, 0.3),  # unc
                  d=(dq.NONE, dq.NONE, dq.NONE)  # dq
                  )

    # Create a Datum holding 0.2 +/- 0.01. We could do this with Datum.k() but it's
    # good to see it in full
    v = Datum(Datum.NUMBER, Value(0.2, 0.01), Datum.null)
    # Wrap an existing ImageCube in a Datum and calculate the sine of all pixels
    imgD = Datum(Datum.IMG, myImageCube).sin()
    # Multiply the two Datum objects together and add 0.3
    out = (v * imgD) + 0.3

    # same calculation in shorthand
    out2 = Datum.k(0.2, 0.01) * Datum(Datum.IMG, myImageCube).sin() + 0.3

    # difference the images, find the abs of all the pixels, find the mean of the differences in each band,
    # and the mean of the mean differences as a single number. Ignore uncertainty. Must be zero.
    mdiff = (out-out2).abs().mean().mean().get(Datum.NUMBER).n
    assert np.isclose(mdiff, 0.0)