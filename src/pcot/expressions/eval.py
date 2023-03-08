"""This is the application-specific part of the expression parsing system.

Anything in here should be specific to PCOT itself, and all data should be as Datum objects.
"""

import pcot.config
import pcot.operations as operations
from pcot.config import parserhook
from pcot.utils.ops import binop, unop, Operator
from .parse import Parser, execute

# TODO: keep expression guide in help updated


@parserhook
def registerBuiltinOperators(p):
    p.registerBinop('+', 10, lambda a, b: binop(Operator.ADD, a, b))
    p.registerBinop('-', 10, lambda a, b: binop(Operator.SUB, a, b))
    p.registerBinop('/', 20, lambda a, b: binop(Operator.DIV, a, b))
    p.registerBinop('*', 20, lambda a, b: binop(Operator.MUL, a, b))
    p.registerBinop('^', 30, lambda a, b: binop(Operator.POW, a, b))
    p.registerUnop('-', 50, lambda a: unop(Operator.NEG, a))

    # standard fuzzy operators (i.e. Zadeh)
    p.registerBinop('&', 20, lambda a, b: binop(Operator.AND, a, b))
    p.registerBinop('|', 20, lambda a, b: binop(Operator.OR, a, b))
    p.registerUnop('!', 50, lambda a: unop(Operator.NOT, a))

    p.registerBinop('$', 100, lambda a, b: binop(Operator.DOLLAR, a, b))


class ExpressionEvaluator(Parser):
    """The core class for the expression evaluator, based on a generic Parser. The constructor
    is responsible for registering most functions."""

    def __init__(self):
        """Initialise the evaluator, registering functions and operators.
        Caller may add other things (e.g. variables)"""
        super().__init__(True)  # naked identifiers permitted

        # additional functions and properties - this is in the __init__.py in the operations package.
        # These are "operations" which take a subimage and perform an operation on that subimage to
        # return another subimage.
        operations.registerOpFunctionsAndProperties(self)

        # generally used for user plugins.
        print("Registering function plugins")
        for x in pcot.config.exprFuncHooks:
            print(f"Calling   {x}")
            x(self)

    def run(self, s):
        """Parse and evaluate an expression."""
        self.parse(s)

        stack = []
        return execute(self.output, stack)
