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
from pcot.expressions.parse import Parser, CompiledExpression

# TODO: keep expression guide in help updated
from pcot.datum import Datum
from pcot.xform import XFormException

logger = logging.getLogger(__name__)


@parserhook
def registerBuiltinOperatorSyntax(p):

    # these are already present in the underlying parser as
    # basic syntax

    p.registerBinop('+', lambda a, b: binop(Operator.ADD, a, b))
    p.registerBinop('-', lambda a, b: binop(Operator.SUB, a, b))
    p.registerBinop('/', lambda a, b: binop(Operator.DIV, a, b))
    p.registerBinop('*', lambda a, b: binop(Operator.MUL, a, b))
    p.registerBinop('^', lambda a, b: binop(Operator.POW, a, b))
    p.registerUnop('-', lambda a: unop(Operator.NEG, a))

    # these are additional operators and so need precedences
    # defined and registered with the low-level parser.

    # standard fuzzy operators (i.e. Zadeh). Very low precedence.
    p.register_infix_left_associative('&', 20)
    p.register_infix_left_associative('|', 20)
    p.registerBinop('&', lambda a, b: binop(Operator.AND, a, b))
    p.registerBinop('|', lambda a, b: binop(Operator.OR, a, b))

    # band-extract operator, binds tight
    p.register_infix_left_associative('$', 250)
    p.registerBinop('$', lambda a, b: binop(Operator.DOLLAR, a, b))

    # comparison operators, binds loose
    p.register_infix_left_associative('<', 50)
    p.register_infix_left_associative('>', 50)
    p.registerBinop('<', lambda a, b: binop(Operator.LESSTHAN, a, b))
    p.registerBinop('>', lambda a, b: binop(Operator.GREATERTHAN, a, b))

    p.register_prefix("!", 175)
    p.registerUnop('!', lambda a: unop(Operator.NOT, a))



def unboundVar():
    """Placeholder VALUE (see below) for a variable registered only so ExpressionEvaluator.compile() resolves
    its name to a rebindable InstVar - not because it has a real value yet. Raises if actually
    executed, so a compiled expression run before being properly rebound fails loudly instead of
    silently using stale or meaningless data. Stateless, so a single reference can be reused for
    any number of variables/expressions.

    Although it should be obvious, NEVER call this function - just use it as a value in variable bindings
    like this:
                expressionParser.compile("a*10",{"a": unboundVar})
    """
    raise RuntimeError("expression variable read before being bound (see ExpressionEvaluator.compile)")


class ExpressionEvaluator(Parser):
    """The core class for the expression evaluator, based on a generic Parser. The constructor
    is responsible for registering most functions."""

    def __init__(self):
        """Initialise the evaluator, registering functions and operators.
        Caller may add other things (e.g. variables)"""
        super().__init__()

        # we register "none" as a variable for all parsers
        self.registerVar("none", "the null value", lambda: Datum.null)

        # now register things that have been marked with the @parserhook decorator.
        logger.debug("Registering function plugins")
        for x in pcot.config.exprFuncHooks:
            #  print(f"Calling   {x}")
            x(self)

    @staticmethod
    def _getvar(d):
        """check that a variable is not ANY (unwired). Also, if it's an image, make a shallow copy (see Issue #56, #65)"""
        if d.tp == Datum.ANY:
            raise XFormException("DATA",
                                 "ANY not permitted as an expression variable type. Unconnected input in expr node?")
        elif d.tp == Datum.IMG:
            if d.val is not None:
                d = Datum(Datum.IMG, d.val.shallowCopy())
        return d

    def _registerVars(self, varDict: Dict[str, Union[Datum, Callable[[], Datum]]] = None,
                       descDict: Dict[str, str] = None):
        """Register (or rebind, if already registered - see Parser.registerVar) each entry in varDict
        as a parser variable."""
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
                    self.registerVar(k, desc, partial(lambda xx: self._getvar(xx), v))

    def compile(self, s: str, varDict: Dict[str, Union[Datum, Callable[[], Datum]]] = None,
                descDict: Dict[str, str] = None) -> CompiledExpression:
        """Register any given variables, then parse (but do not run) an expression, returning
        a CompiledExpression which can be executed - possibly many times, and with rebound
        variables (see registerVar) - without re-parsing. See run() for the argument meanings.

        Any variable name the expression is meant to reference later must be given a value
        (even a placeholder) in varDict here: naked identifiers are permitted in this parser,
        so a name that isn't registered at compile time is baked in as a literal string
        (InstIdent) rather than a rebindable variable reference, and later registerVar() calls
        for that name won't affect the compiled expression. If the placeholder shouldn't ever
        actually be used, register unboundVar (see above) as its value, so premature execution
        fails loudly rather than silently using stale or meaningless data."""
        self._registerVars(varDict, descDict)
        return super().compile(s)

    def run(self, s: Union[str, CompiledExpression],
            varDict: Dict[str, Union[Datum, Callable[[], Datum]]] = None, descDict: Dict[str, str] = None) -> Datum:
        """Parse (if necessary) and evaluate an expression:

         - s is the expression, either as a string (parsed fresh each call) or a
           CompiledExpression obtained from compile() (parsing is skipped)

         The following two arguments are not used by the expression node, but by libraries.

         - varDict is an optional dictionary of string to Datum or Callable for assigning variables
         - descDict is an optional dictionary providing descriptions for the variables in varDict
         """
        if isinstance(s, CompiledExpression):
            self._registerVars(varDict, descDict)
            return s.execute()

        compiled = self.compile(s, varDict, descDict)
        return compiled.execute()


def evaluateOnImage(img: ImageCube, expr: Union[str, CompiledExpression]) -> Datum:
    """Function for running a simple expression on an image; the image is passed in as variable "a".
    expr may be a string (parsed fresh) or a CompiledExpression from ExpressionEvaluator.compile()
    (parsing is skipped, and "a" is rebound to the new image)."""
    e = ExpressionEvaluator()
    dat = Datum(Datum.IMG, img)
    r = e.run(expr, {"a": dat})
    return r