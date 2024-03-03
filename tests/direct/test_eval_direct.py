"""
Test "direct" use of the expression evaluator, outside an expr node
"""
import numpy as np
import pytest

import pcot
from pcot import dq
from pcot.datum import Datum
from pcot.expressions import ExpressionEvaluator
from pcot.filters import Filter
from pcot.sources import nullSourceSet, Source, MultiBandSource
from pcot.value import Value
from fixtures import genrgb


def test_evaluator_inline():
    """Test the evaluator in "inline" mode with both images and numbers"""
    pcot.setup()

    e = ExpressionEvaluator()
    r = e.run("sqrt(a+b+2)",
              {
                  # check it works with both a Datum
                  'a': Datum(Datum.NUMBER, Value(10.0, 0.1), nullSourceSet),
                  # and a lambda that returns a datum
                  'b': lambda: Datum(Datum.NUMBER, Value(4.0, 0.2), nullSourceSet)
              })
    v = r.get(Datum.NUMBER)
    assert np.allclose(4.0, v.n)
    assert np.allclose(0.02795085, v.u)
    assert v.dq == 0

    # now for images

    # make a 32x32x3 image with RGB 3,2,1
    img = genrgb(32, 32, 3, 2, 1)
    r = e.run("(a$R)*b",
                {
                    'a': Datum(Datum.IMG, img),
                    'b': Datum(Datum.NUMBER, Value(2.0, 0.1), nullSourceSet)
                })
    v = r.get(Datum.IMG)
    assert np.allclose(v.img[0, 0], 6)
    assert np.allclose(v.uncertainty[0, 0], 0.3)
    assert v.dq[0, 0] == dq.NOUNCERTAINTY


def test_datum_operators():
    """Test that operator overloading on Datum works"""

    a = Datum(Datum.NUMBER, Value(10.0, 0.1), nullSourceSet)
    b = Datum(Datum.NUMBER, Value(4.0, 0.2), nullSourceSet)

    r = a + b
    assert np.allclose(14.0, r.get(Datum.NUMBER).n)
    assert np.allclose(0.2236068, r.get(Datum.NUMBER).u)

    r = a - b
    assert np.allclose(6.0, r.get(Datum.NUMBER).n)
    assert np.allclose(0.2236068, r.get(Datum.NUMBER).u)

    r = a * b
    assert np.allclose(40.0, r.get(Datum.NUMBER).n)
    assert np.allclose(2.0396, r.get(Datum.NUMBER).u)

    r = a / b
    assert np.allclose(2.5, r.get(Datum.NUMBER).n)
    assert np.allclose(0.12747548783982, r.get(Datum.NUMBER).u)

    r = a ** b
    assert np.allclose(10000.0, r.get(Datum.NUMBER).n)
    assert np.allclose(4622.50932, r.get(Datum.NUMBER).u)

    r = a * -b
    assert np.allclose(-40.0, r.get(Datum.NUMBER).n)
    assert np.allclose(2.0396, r.get(Datum.NUMBER).u)

    r = -a * b
    assert np.allclose(-40.0, r.get(Datum.NUMBER).n)
    assert np.allclose(2.0396, r.get(Datum.NUMBER).u)

    r = -(a * b)
    assert np.allclose(-40.0, r.get(Datum.NUMBER).n)
    assert np.allclose(2.0396, r.get(Datum.NUMBER).u)

    r = ~a          # careful, it's not "not". A bit weird, it calculates (1-x). This is a fuzzy NOT.
    assert np.allclose(-9.0, r.get(Datum.NUMBER).n)
    assert np.allclose(0.1, r.get(Datum.NUMBER).u)

    r = a & b       # calculates a fuzzy AND
    assert np.allclose(4.0, r.get(Datum.NUMBER).n)
    assert np.allclose(0.2, r.get(Datum.NUMBER).u)

    r = a | b       # calculates a fuzzy OR
    assert np.allclose(10.0, r.get(Datum.NUMBER).n)
    assert np.allclose(0.1, r.get(Datum.NUMBER).u)


def test_datum_and_number():
    a = Datum(Datum.NUMBER, Value(10.0, 0.1), nullSourceSet)
    r = 2 / a       # test that it works with a number on the LHS
    assert np.allclose(0.2, r.get(Datum.NUMBER).n)
    assert np.allclose(0.002, r.get(Datum.NUMBER).u)

    r = a * 2       # test that it works with a number on the RHS
    assert np.allclose(20.0, r.get(Datum.NUMBER).n)
    assert np.allclose(0.2, r.get(Datum.NUMBER).u)


def test_band_extract():
    d = Datum(Datum.IMG, genrgb(32, 32, 3, 2, 1))
    r = d % "_0"  # extract the red band
    v = r.get(Datum.IMG)
    assert np.allclose(v.img[0, 0], 3)

    # now generate another image with wavelengths assigned to RGB

    img = genrgb(32, 32, 3, 2, 1)
    red = Source().setBand(Filter(640, 1.0, name="red"))
    green = Source().setBand(Filter(540, 1.0, name="green"))
    blue = Source().setBand(Filter(440, 1.0, name="blue"))
    img.sources = MultiBandSource([red, green, blue])

    # and test that the band extraction works with wavelengths

    r = Datum(Datum.IMG, img) % 540
    v = r.get(Datum.IMG)
    assert np.allclose(v.img[0, 0], 2)


def test_func_call():
    from pcot.expressions.builtins import testimg
    d = testimg(0)
    img = d.get(Datum.IMG)
    assert img is not None
    assert img.channels == 3
