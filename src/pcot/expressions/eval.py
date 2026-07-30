"""This is the application-specific part of the expression parsing system.

Anything in here should be specific to PCOT itself, and all data should be as Datum objects.
"""
import logging
from functools import partial
from typing import Dict, Callable, Union

import pcot.config
from pcot.imagecube import ImageCube
from pcot.config import parserhook
from pcot.expressions.ops import binop, unop, Operator
from pcot.expressions.parse import Parser, execute

# TODO: keep expression guide in help updated
from ..datum import Datum
from ..xform import XFormException

logger = logging.getLogger(__name__)


@parserhook
def registerBuiltinOperatorSyntax(p):
    p.registerBinop('+', 10, lambda a, b: binop(Operator.ADD, a, b))
    p.registerBinop('-', 10, lambda a, b: binop(Operator.SUB, a, b))
    p.registerBinop('/', 20, lambda a, b: binop(Operator.DIV, a, b))
    p.registerBinop('*', 20, lambda a, b: binop(Operator.MUL, a, b))
    p.registerBinop('^', 30, lambda a, b: binop(Operator.POW, a, b))


    # standard fuzzy operators (i.e. Zadeh)
    p.registerBinop('&', 20, lambda a, b: binop(Operator.AND, a, b))
    p.registerBinop('|', 20, lambda a, b: binop(Operator.OR, a, b))

    p.registerBinop('$', 60, lambda a, b: binop(Operator.DOLLAR, a, b))

    # comparison operators
    p.registerBinop('<', 60, lambda a, b: binop(Operator.LESSTHAN, a, b))
    p.registerBinop('>', 60, lambda a, b: binop(Operator.GREATERTHAN, a, b))

    # unary ops bind tight
    p.registerUnop('-', 70, lambda a: unop(Operator.NEG, a))
    p.registerUnop('!', 80, lambda a: unop(Operator.NOT, a))

class ExpressionEvaluator(Parser):
    """The core class for the expression evaluator, based on a generic Parser. The constructor
    is responsible for registering most functions."""

    def __init__(self):
        """Initialise the evaluator, registering functions and operators.
        Caller may add other things (e.g. variables)"""
        super().__init__(True)  # naked identifiers permitted

        # we register "none" as a variable for all parsers
        self.registerVar("none", "the null value", lambda: Datum.null)

        # now register things that have been marked with the @parserhook decorator.
        logger.debug("Registering function plugins")
        for x in pcot.config.exprFuncHooks:
            #  print(f"Calling   {x}")
            x(self)

    def run(self, s, varDict: Dict[str, Union[Datum, Callable[[], Datum]]] = None, descDict: Dict[str, str] = None):
        """Parse and evaluate an expression:

         - s is the expression

         The following two arguments are not used by the expression node, but by libraries.

         - varDict is an optional dictionary of string to Datum or Callable for assigning variables
         - descDict is an optional dictionary providing descriptions for the variables in varDict
         """

        def getvar(d):
            """check that a variable is not ANY (unwired). Also, if it's an image, make a shallow copy (see Issue #56, #65)"""
            if d.tp == Datum.ANY:
                raise XFormException("DATA",
                                     "ANY not permitted as an expression variable type. Unconnected input in expr node?")
            elif d.tp == Datum.IMG:
                if d.val is not None:
                    d = Datum(Datum.IMG, d.val.shallowCopy())
            return d

        if varDict:
            for k, v in varDict.items():
                # if there's no description just use the name again
                desc = descDict[k] if descDict and k in descDict else k
                # register a lambda to return the value if it isn't callable - it will also try to
                # ensure that a shallow copy is made of images (just as the expr node does). And we have
                # the late binding problem here too!
                if callable(v):
                    self.registerVar(k, desc, v)
                else:
                    self.registerVar(k, desc, partial(lambda xx: getvar(xx), v))

        self.parse(s)
        stack = []
        return execute(self.output, stack)


def evaluateOnImage(img: ImageCube, expr: str) -> Datum:
    """Function for running a simple expression on an image; the image is passed in as variable "a"
    """
    e = ExpressionEvaluator()
    dat = Datum(Datum.IMG, img)
    r = e.run(expr, {"a": dat})
    return r