"""
Parser/Evaluator tests - not PCOT specific, just the shunting yard algorithm and VM.
"""
from math import sqrt

import parse
import unittest

variable_1 = 0
variable_2 = 0


def execute(s, nakedIdents=False):
    p = parse.Parser(nakedIdents=nakedIdents)
    p.registerFunc('sqrt', lambda a: sqrt(a[0]))
    p.registerFunc('sqr', lambda a: a[0] * a[0])
    p.registerFunc('max', lambda a: max(a))
    p.registerFunc('min', lambda a: min(a))
    p.registerFunc('firstarg',lambda a: a[0])
    p.registerFunc('lastarg',lambda a: a[-1])
    p.registerFunc('noargs',lambda a: 100)
    p.registerBinop('*', 20, lambda a, b: a * b)
    p.registerBinop('/', 20, lambda a, b: a / b)
    p.registerBinop('+', 10, lambda a, b: a + b)
    p.registerBinop('-', 10, lambda a, b: a - b)
    p.registerUnop('-', 200, lambda a: -a)
    p.registerVar('var1', lambda: variable_1)
    p.registerVar('var2', lambda: variable_2)

    p.parse(s)

    stack = []
    r = parse.execute(p.output, stack)
    return r


class TestBasic(unittest.TestCase):
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
        variable_1 = 10
        self.assertEqual(execute('var1'), 10)

    def test_2(self):
        global variable_1
        global variable_2
        variable_1 = 10
        variable_2 = 21
        self.assertEqual(execute('var1-var2'), -11)

    def test_3(self):
        global variable_1
        global variable_2
        variable_1 = 10
        variable_2 = 21
        self.assertEqual(execute('var1-(var2)'), -11)

    def test_4(self):
        global variable_1
        global variable_2
        variable_1 = 10
        variable_2 = 21
        self.assertEqual(execute('var1-(var2/2)'), -0.5)


class TestNakedIdents(unittest.TestCase):
    def test_1(self):
        self.assertEqual(execute('foo', True), 'foo')

    def test_2(self):
        self.assertRaises(parse.ParseException, lambda: execute('foo'))

    def test_3(self):
        # not much point to this, but hey.
        self.assertEqual(execute('blart+foo', True), 'blartfoo')


class TestFunctions(unittest.TestCase):
    def test_1(self):
        self.assertEqual(execute('sqrt(16)'), 4)

    def test_2(self):
        self.assertEqual(execute('min(45,1,56,12,2)'), 1)

    def test_3(self):
        self.assertEqual(execute('max(45,1,56,12,2)'), 56)

    def test_4(self):
        self.assertEqual(execute('firstarg(45,1,56,12,2)'), 45)

    def test_5(self):
        self.assertEqual(execute('lastarg(45,1,56,12,2)'), 2)

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
