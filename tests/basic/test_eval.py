"""
Parser/Evaluator tests - not PCOT specific, just the shunting yard algorithm and VM.
This was written with unittest, but you don't need to write every test suite that way -
it's just that this was done first.

Note that there are a lot of tests for how expr nodes manage sources in test_source_principles.py
"""
from math import sqrt
import unittest
from typing import Callable, Any, Optional, Type

from pcot.datum import Datum
from pcot.expressions import parse, Parameter
from pcot.number import Number
from pcot.sources import nullSourceSet


def mknumFloat(n: float):
    """Create a null source set numerical datum from a float for testing"""
    return Datum(Datum.NUMBER, Number(n, 0), sources=nullSourceSet)

def mknumNum(n: Number):
    """Create a null source set numerical datum from a Number for testing"""
    return Datum(Datum.NUMBER, n, sources=nullSourceSet)

variable_1 = mknumFloat(0)
variable_2 = mknumFloat(0)


def binop(a: Datum, b: Datum, op: Callable[[Any, Any], Any]) -> Datum:
    assert a.tp == Datum.NUMBER
    assert b.tp == Datum.NUMBER
    return mknumNum(op(a.get(Datum.NUMBER), b.get(Datum.NUMBER)))


def execute(s, nakedIdents=False):
    p = parse.Parser(nakedIdents=nakedIdents)
    p.registerFunc("sqrt", "calculate the square root",
                   [Parameter("angle", "value(s) to input", Datum.NUMBER)],
                   [],
                   lambda args, optargs: mknumFloat(sqrt(args[0].get(Datum.NUMBER).n)))

    p.registerFunc("min", "find the minimum value of pixels in a list of ROIs, images or values",
                   [Parameter("val", "value(s) to input", Datum.NUMBER)],
                   [],
                   lambda args, optargs: mknumFloat(min([x.get(Datum.NUMBER).n for x in args])), True)
    p.registerFunc("max", "find the maximum value of pixels in a list of ROIs, images or values",
                   [Parameter("val", "value(s) to input", Datum.NUMBER)],
                   [],
                   lambda args, optargs: mknumFloat(max([x.get(Datum.NUMBER).n for x in args])), True)
    p.registerFunc("noargs", "just return a constant",
                   [],
                   [],
                   lambda args, optargs: mknumFloat(100.0), False)

    p.registerBinop('+', 10, lambda a, b: binop(a, b, lambda x, y: x + y))
    p.registerBinop('-', 10, lambda a, b: binop(a, b, lambda x, y: x - y))
    p.registerBinop('/', 20, lambda a, b: binop(a, b, lambda x, y: x / y))
    p.registerBinop('*', 20, lambda a, b: binop(a, b, lambda x, y: x * y))
    p.registerUnop('-', 200, lambda a: mknumFloat(-(a.get(Datum.NUMBER).n)))
    p.registerVar('var1', "test var", lambda: variable_1)
    p.registerVar('var2', "test var", lambda: variable_2)

    p.parse(s)

    stack = []
    r = parse.execute(p.output, stack)
    # if the returned value is a number, extract it. Otherwise just return the Datum.
    if r.tp == Datum.NUMBER:
        return r.get(Datum.NUMBER).n
    else:
        return r


class TestCoreBinops(unittest.TestCase):
    def test_add(self):
        self.assertEqual(execute('6+6'), 12.0)

    def test_sub(self):
        self.assertEqual(execute('8-2'), 6.0)

    def test_mul(self):
        self.assertEqual(execute('8*4'), 32.0)

    def test_div(self):
        self.assertEqual(execute('16/2'), 8.0)


class TestAssociative(unittest.TestCase):
    def test_1(self):
        self.assertEqual(execute('10*12+4*3'), 132.0)

    def test_2(self):
        self.assertEqual(execute('10*(12+4)*3'), 480.0)

    def test_3(self):
        self.assertEqual(execute('(2+2)*(3+3)'), 24.0)

    def test_4(self):
        self.assertEqual(execute('10/2+9/3'), 8.0)

    def test_5(self):
        self.assertEqual(execute('10/2-9/3'), 2.0)

    def test_6(self):
        self.assertEqual(execute('10*(9-2)*3'), 210.0)

    def test_7(self):
        self.assertEqual(execute('(10-2)*2'), 16.0)

    def test_8(self):
        self.assertEqual(execute('10-2*2'), 6.0)


class TestUnaryMinus(unittest.TestCase):
    def test_1(self):
        self.assertEqual(execute('-43'), -43)

    def test_2(self):
        self.assertEqual(execute('-43+10'), -33)

    def test_3(self):
        self.assertEqual(execute('43*-1'), -43)

    def test_4(self):
        self.assertEqual(execute('43+-3'), 40)

    def test_5(self):
        self.assertEqual(execute('-4--3'), -1)

    def test_6(self):
        self.assertEqual(execute('(-4)'), -4)

    def test_7(self):
        self.assertEqual(execute('-(-4)'), 4)

    def test_8(self):
        self.assertEqual(execute('-(2*8)'), -16)

    def test_9(self):
        self.assertEqual(execute('-(2*-8)'), 16)


class TestVariables(unittest.TestCase):
    def test_1(self):
        global variable_1
        variable_1 = mknumFloat(10)
        self.assertEqual(execute('var1'), 10)

    def test_2(self):
        global variable_1
        global variable_2
        variable_1 = mknumFloat(10)
        variable_2 = mknumFloat(21)
        self.assertEqual(execute('var1-var2'), -11)

    def test_3(self):
        global variable_1
        global variable_2
        variable_1 = mknumFloat(10)
        variable_2 = mknumFloat(21)
        self.assertEqual(execute('var1-(var2)'), -11)

    def test_4(self):
        global variable_1
        global variable_2
        variable_1 = mknumFloat(10)
        variable_2 = mknumFloat(21)
        self.assertEqual(execute('var1-(var2/2)'), -0.5)


class TestNakedIdents(unittest.TestCase):
    def test_1(self):
        self.assertEqual(execute('foo', True).get(Datum.IDENT), 'foo')

    def test_2(self):
        self.assertRaises(parse.ParseException, lambda: execute('foo'))


class TestFunctions(unittest.TestCase):
    def test_1(self):
        self.assertEqual(execute('sqrt(16)'), 4)

    def test_2(self):
        self.assertEqual(execute('min(45,1,56,12,2)'), 1)

    def test_3(self):
        self.assertEqual(execute('max(45,1,56,12,2)'), 56)

    def test_6(self):
        self.assertEqual(execute('10+noargs()'), 110)

    def test_7(self):
        self.assertEqual(execute('max(1,2,4+7,5+1,2*6)'), 12)

    def test_8(self):
        self.assertEqual(execute('max(1,2,4+7,2*6,5+1)'), 12)

    def test_9(self):
        self.assertEqual(execute('max(1,2,4+7,min(100,50,200),5+1)'), 50)

    def test_10(self):
        self.assertEqual(execute('max(0,3,2)+min(7,2,45,3)'), 5)

    def test_11(self):
        self.assertEqual(execute('max(min(100,50,200),1,2,4+7,5+1)'), 50)

    def test_12(self):
        self.assertEqual(execute('max(1,2,4+7,5+1,min(100,50,200))'), 50)


if __name__ == '__main__':
    unittest.main()
