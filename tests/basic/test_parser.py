"""
Tests for the Pratt parser in parser.py.

Each test parses an expression and runs it through TestVisitor, asserting on the
resulting stack-instruction string list. This exercises precedence/associativity/
grouping through the same code path a real code generator would use, without
depending on TreeNode's internal shape.
"""
import unittest

from pcot.expressions.prattparser import PrattParser, TestVisitor, ParserException


def rpn(expr: str) -> list:
    p = PrattParser()
    p.register_infix_left_associative("-", 100)
    p.register_infix_left_associative("+", 100)
    p.register_infix_left_associative("*", 150)
    p.register_infix_left_associative("/", 150)
    p.register_infix_right_associative("^", 200)
    p.register_prefix("-", 175)

    tree = p.parse(expr)
    return TestVisitor().visit(tree)


class PrecedenceTests(unittest.TestCase):
    def test_left_associative_plus_minus(self):
        self.assertEqual(rpn("a-b+c"), ['name:"a"', 'name:"b"', 'binop:-', 'name:"c"', 'binop:+'])
        self.assertEqual(rpn("a+b-c"), ['name:"a"', 'name:"b"', 'binop:+', 'name:"c"', 'binop:-'])

    def test_left_associative_mul_div(self):
        self.assertEqual(rpn("a*b/c"), ['name:"a"', 'name:"b"', 'binop:*', 'name:"c"', 'binop:/'])
        self.assertEqual(rpn("a/b*c"), ['name:"a"', 'name:"b"', 'binop:/', 'name:"c"', 'binop:*'])

    def test_mul_binds_tighter_than_add(self):
        self.assertEqual(rpn("a+b*c"), ['name:"a"', 'name:"b"', 'name:"c"', 'binop:*', 'binop:+'])

    def test_right_associative_power(self):
        self.assertEqual(rpn("a^b^c"), ['name:"a"', 'name:"b"', 'name:"c"', 'binop:^', 'binop:^'])

    def test_power_binds_tighter_than_mul(self):
        self.assertEqual(rpn("a*b^c"), ['name:"a"', 'name:"b"', 'name:"c"', 'binop:^', 'binop:*'])


class UnaryMinusTests(unittest.TestCase):
    def test_binds_tighter_than_mul(self):
        self.assertEqual(rpn("-a*b"), ['name:"a"', 'unop:-', 'name:"b"', 'binop:*'])

    def test_binds_tighter_than_add(self):
        self.assertEqual(rpn("-a+b"), ['name:"a"', 'unop:-', 'name:"b"', 'binop:+'])

    def test_binds_looser_than_power(self):
        self.assertEqual(rpn("-a^b"), ['name:"a"', 'name:"b"', 'binop:^', 'unop:-'])

    def test_binds_looser_than_call(self):
        self.assertEqual(rpn("-f(x)"), ['name:"x"', 'name:"f"', 'call:n=2', 'unop:-'])


class GroupingApplicationTests(unittest.TestCase):
    def test_parenthesised_group_overrides_precedence(self):
        self.assertEqual(rpn("(a+b)*c"), ['name:"a"', 'name:"b"', 'binop:+', 'name:"c"', 'binop:*'])

    def test_function_call_with_args(self):
        self.assertEqual(rpn("f(x,y)"), ['name:"x"', 'name:"y"', 'name:"f"', 'call:n=3'])

    def test_function_call_no_args(self):
        self.assertEqual(rpn("f()"), ['name:"f"', 'call:n=1'])

    def test_function_call_args_are_full_expressions(self):
        self.assertEqual(
            rpn("f(a+b,c*d)"),
            ['name:"a"', 'name:"b"', 'binop:+', 'name:"c"', 'name:"d"', 'binop:*', 'name:"f"', 'call:n=3'],
        )

    def test_indexing(self):
        self.assertEqual(rpn("a[i]"), ['name:"i"', 'name:"a"', 'index:n=2'])

    def test_nested_function_calls(self):
        self.assertEqual(
            rpn("f(g(x,y),z)"),
            ['name:"x"', 'name:"y"', 'name:"g"', 'call:n=3', 'name:"z"', 'name:"f"', 'call:n=3'],
        )


class VectorTests(unittest.TestCase):
    def test_vector_of_full_expressions(self):
        self.assertEqual(
            rpn("[1,2,3,2*2,a*b]"),
            ['num:1', 'num:2', 'num:3', 'num:2', 'num:2', 'binop:*',
             'name:"a"', 'name:"b"', 'binop:*', 'vector:n=5'],
        )

    def test_empty_vector(self):
        self.assertEqual(rpn("[]"), ['vector:n=0'])

    def test_nested_vector(self):
        self.assertEqual(rpn("[[1,2],3]"), ['num:1', 'num:2', 'vector:n=2', 'num:3', 'vector:n=2'])

    def test_vector_as_function_argument(self):
        self.assertEqual(rpn("f([1,2])"), ['num:1', 'num:2', 'vector:n=2', 'name:"f"', 'call:n=2'])

    def test_indexing_still_works_alongside_vector_literal(self):
        self.assertEqual(rpn("a[i]"), ['name:"i"', 'name:"a"', 'index:n=2'])


class LiteralTests(unittest.TestCase):
    def test_number(self):
        self.assertEqual(rpn("2+3"), ['num:2', 'num:3', 'binop:+'])

    def test_string_is_dequoted(self):
        self.assertEqual(rpn('"hi"+x'), ['string:"hi"', 'name:"x"', 'binop:+'])
        self.assertEqual(rpn("'hi'+x"), ['string:"hi"', 'name:"x"', 'binop:+'])


class ErrorTests(unittest.TestCase):
    def test_unregistered_operator_raises(self):
        with self.assertRaises(ParserException):
            rpn("a%2")

    def test_unclosed_bracket_raises(self):
        with self.assertRaises(ParserException):
            rpn("(a+b")

    def test_trailing_tokens_raise(self):
        with self.assertRaises(ParserException):
            rpn("a b")


if __name__ == "__main__":
    unittest.main()
