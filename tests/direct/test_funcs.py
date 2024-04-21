import numpy as np
import pytest

import pcot
from pcot.datum import Datum
from pcot.dq import NOUNCERTAINTY, ERROR
from pcot.expressions import ExpressionEvaluator
from pcot.datumfuncs import testimg
from pcot.expressions.register import datumfunc
from pcot.expressions.parse import ArgsException
from pcot.sources import nullSourceSet

"""
Test datum functions by defining a test function and using it both from the test code and from the expression evaluator.
Also tests testimg() and Datum.k().
"""


@datumfunc
def testfunc1(a, b, c=1.0):
    """
    function that takes two images and adds them, with an optional number which it multiplies by.
    @param a: img: image 1
    @param b: img,number: image 2
    @param c: number: optional number to multiply by
    """

    # and then use the Datum operator overloads
    return (a + b) * c


@datumfunc
def testfunc2(first, *args):
    """
    function that takes any number of arguments and adds them together, but the first
    must be an image.

    @param first: img: the first image

    """

    assert first.tp == Datum.IMG
    d = first.copy()
    for a in args:
        d += a
        # make sure the original is unchanged
        assert d.get(Datum.IMG)[0, 0] != args[0].get(Datum.IMG)[0, 0]
    return d


def test_k():
    d = Datum.k(0)
    assert d.get(Datum.NUMBER).n == 0
    assert d.get(Datum.NUMBER).u == 0
    assert d.get(Datum.NUMBER).dq == NOUNCERTAINTY
    assert d.sources == nullSourceSet

    d = Datum.k(1, 0.1)
    assert d.get(Datum.NUMBER).n == 1
    assert np.allclose(d.get(Datum.NUMBER).u, 0.1)
    assert d.get(Datum.NUMBER).dq == 0

    d = Datum.k(2, 0.01, dq=ERROR)
    assert d.get(Datum.NUMBER).n == 2
    assert np.allclose(d.get(Datum.NUMBER).u, 0.01)
    assert d.get(Datum.NUMBER).dq == ERROR

    d = Datum.k(2, 0.0, dq=ERROR)
    assert d.get(Datum.NUMBER).n == 2
    assert np.allclose(d.get(Datum.NUMBER).u, 0.0)
    assert d.get(Datum.NUMBER).dq == ERROR | NOUNCERTAINTY


def test_func_call():
    from pcot.datumfuncs import testimg
    d = testimg(Datum.k(0))  # k is used to generate constants
    img = d.get(Datum.IMG)
    assert img is not None
    assert img.channels == 3


def test_optional_arg_in_expr():
    pcot.setup()
    e = ExpressionEvaluator()

    # first, get a reference value for a single pixel in the test image.
    r = e.run("testimg(0)", {}).get(Datum.IMG)
    assert r is not None
    red, green, blue = r[10, 10]
    assert red.dq == NOUNCERTAINTY
    assert green.dq == NOUNCERTAINTY
    assert blue.dq == NOUNCERTAINTY

    assert red.u == 0
    assert green.u == 0
    assert blue.u == 0

    assert np.allclose(red.n, 0.37254902720451355)
    assert np.allclose(green.n, 0.1764705926179886)
    assert np.allclose(blue.n, 0.10196078568696976)

    # record the original colours of the pixel
    imgr = red.n
    imgg = green.n
    imgb = blue.n

    # now test the more complex expression with the argument holding a default.
    # It should just sum the image with itself.
    r = e.run("testfunc1(testimg(0), testimg(0))", {}).get(Datum.IMG)
    red, green, blue = r[10, 10]
    assert np.allclose(red.n, imgr * 2)
    assert np.allclose(green.n, imgg * 2)
    assert np.allclose(blue.n, imgb * 2)

    # and now I'll add the more complex case where the optional argument is used.
    r = e.run("testfunc1(testimg(0), testimg(0), 3.0)", {}).get(Datum.IMG)
    red, green, blue = r[10, 10]
    assert np.allclose(red.n, imgr * 2 * 3)
    assert np.allclose(green.n, imgg * 2 * 3)
    assert np.allclose(blue.n, imgb * 2 * 3)

    # now do it again, but this time use a number instead of an image for the second argument
    r = e.run("testfunc1(testimg(0), 5.0, 7.0)", {}).get(Datum.IMG)
    red, green, blue = r[10, 10]
    assert np.allclose(red.n, (imgr + 5) * 7)
    assert np.allclose(green.n, (imgg + 5) * 7)
    assert np.allclose(blue.n, (imgb + 5) * 7)

    # but using a number for the first argument should fail
    with pytest.raises(ArgsException):
        e.run("testfunc1(5.0, testimg(0), 7.0)", {}).get(Datum.IMG)

    # also for the default case
    with pytest.raises(ArgsException):
        e.run("testfunc1(testimg(0), testimg(0), testimg(0))", {}).get(Datum.IMG)


def test_direct():
    """Test the testfunction directly. Very similar to the previous test, but without the expression evaluator."""
    r = testimg(Datum.k(0)).get(Datum.IMG)
    assert r is not None
    red, green, blue = r[10, 10]
    assert red.dq == NOUNCERTAINTY
    assert green.dq == NOUNCERTAINTY
    assert blue.dq == NOUNCERTAINTY

    assert red.u == 0
    assert green.u == 0
    assert blue.u == 0

    assert np.allclose(red.n, 0.37254902720451355)
    assert np.allclose(green.n, 0.1764705926179886)
    assert np.allclose(blue.n, 0.10196078568696976)

    # record the original colours of the pixel
    imgr = red.n
    imgg = green.n
    imgb = blue.n

    # now test the more complex expression with the argument holding a default.
    # It should just sum the image with itself.
    r = testfunc1(testimg(0), testimg(0)).get(Datum.IMG)
    red, green, blue = r[10, 10]
    assert np.allclose(red.n, imgr * 2)
    assert np.allclose(green.n, imgg * 2)
    assert np.allclose(blue.n, imgb * 2)

    # and now I'll add the more complex case where the optional argument is used.
    r = testfunc1(testimg(0), testimg(0), 3.0).get(Datum.IMG)
    red, green, blue = r[10, 10]
    assert np.allclose(red.n, imgr * 2 * 3)
    assert np.allclose(green.n, imgg * 2 * 3)
    assert np.allclose(blue.n, imgb * 2 * 3)

    # now do it again, but this time use a number instead of an image for the second argument
    r = testfunc1(testimg(0), 5, 7).get(Datum.IMG)
    red, green, blue = r[10, 10]
    assert np.allclose(red.n, (imgr + 5) * 7)
    assert np.allclose(green.n, (imgg + 5) * 7)
    assert np.allclose(blue.n, (imgb + 5) * 7)

    # but using a number for the first argument should fail
    with pytest.raises(ArgsException):
        testfunc1(5, testimg(0), 7)

    # also for the default case
    with pytest.raises(ArgsException):
        testfunc1(testimg(0), testimg(0), testimg(0))


def test_varargs():
    r = testfunc2(testimg(0)).get(Datum.IMG)
    assert r is not None
    red, green, blue = r[10, 10]
    assert red.dq == NOUNCERTAINTY
    assert green.dq == NOUNCERTAINTY
    assert blue.dq == NOUNCERTAINTY

    assert red.u == 0
    assert green.u == 0
    assert blue.u == 0

    assert np.allclose(red.n, 0.37254902720451355)
    assert np.allclose(green.n, 0.1764705926179886)
    assert np.allclose(blue.n, 0.10196078568696976)

    # record the original colours of the pixel
    imgr = red.n
    imgg = green.n
    imgb = blue.n

    r = testfunc2(testimg(0), testimg(0)).get(Datum.IMG)
    red, green, blue = r[10, 10]
    assert np.allclose(red.n, imgr * 2)
    assert np.allclose(green.n, imgg * 2)
    assert np.allclose(blue.n, imgb * 2)

    r = testfunc2(testimg(0), testimg(0), 3.0).get(Datum.IMG)
    red, green, blue = r[10, 10]
    assert np.allclose(red.n, imgr * 2 + 3.0)
    assert np.allclose(green.n, imgg * 2 + 3.0)
    assert np.allclose(blue.n, imgb * 2 + 3.0)

    r = testfunc2(testimg(0), testimg(0), 3.0, testimg(0)).get(Datum.IMG)
    red, green, blue = r[10, 10]
    assert np.allclose(red.n, imgr * 3 + 3.0)
    assert np.allclose(green.n, imgg * 3 + 3.0)
    assert np.allclose(blue.n, imgb * 3 + 3.0)


@datumfunc
def example_func(a, b=2.0):
    """
    Example function that takes two numbers a,b and returns a+b*2
    @param a: number: first number
    @param b: number: second number
    """
    return a * b


def test_example_func():
    """Test a function that's used in the docs"""
    r = example_func(Datum.k(2), Datum.k(2)).get(Datum.NUMBER)
    assert r.n == 4
    assert r.u == 0
    assert r.dq == NOUNCERTAINTY
    r = example_func(Datum.k(7)).get(Datum.NUMBER)
    assert r.n == 14
    assert r.u == 0
    assert r.dq == NOUNCERTAINTY


@datumfunc
def varargs_nomand_differenttypes(*args):
    """
    Example function
    """

    assert args[0].tp == Datum.NUMBER
    assert args[1].tp == Datum.NUMBER
    assert args[2].tp == Datum.IMG


def test_varargs_nomand_differenttypes():
    """Test a varargs function with no mandatory args and different argument types"""
    a = Datum.k(2)
    b = Datum.k(3)
    img = testimg(0)

    varargs_nomand_differenttypes(a, b, img)


@datumfunc
def stringexample(a, b, op='add'):
    """
    String argument example
    @param a: number: first number
    @param b: number: second number
    @param op: string: operation to perform
    """
    if op.get(Datum.STRING) == 'add':
        return a + b
    elif op.get(Datum.STRING) == 'sub':
        return a - b
    else:
        raise ValueError("Unknown operation")


def test_stringexample():
    """Test an optional string argument"""
    r = stringexample(2, 3, 'add').get(Datum.NUMBER)
    assert r.n == 5
    assert r.u == 0
    assert r.dq == NOUNCERTAINTY

    op = Datum(Datum.STRING, 'sub', sources=nullSourceSet)
    r = stringexample(-2, 4, op).get(Datum.NUMBER)
    assert r.n == -6
    assert r.u == 0
    assert r.dq == NOUNCERTAINTY

    with pytest.raises(ValueError):
        stringexample(1, 1, 'mul')
