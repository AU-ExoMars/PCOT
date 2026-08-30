"""This is the expression parser and VM. Parsing is done by the Pratt parser in
prattparser.py, which produces a generic syntax tree; that tree is then walked
(see Visitor) to produce a sequence of instructions for a stack machine. While
largely application independent, it does use PCOT's Datum type as a variant
record, and conntypes to handle type checking. Help texts are also generated.
"""
from __future__ import annotations

import logging

from typing import List, Any, Optional, Callable, Dict, Tuple

from pcot.datum import Datum
from pcot.datumtypes import Type
from pcot.expressions.instructions import Instruction, Stack, InstNumber, InstString, InstVar, InstIdent, InstBinop, \
    InstUnop, InstCall, InstIndex, InstCreateVector
from pcot.expressions.prattparser import PrattParser, TreeVisitor, TreeNode
from pcot.expressions.types import ParseException, Variable, Function, Parameter
from pcot.utils.table import Table

logger = logging.getLogger(__name__)


def execute(seq: List[Instruction], stack: Stack) -> Datum:
    """Execute a list of instructions on a given stack"""
    for inst in seq:
        logger.debug(f"EXECUTING {inst}")
        inst.exec(stack)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"EXECUTED {inst}, STACK NOW (top shown last):")
            for x in stack:
                logger.debug(f"    {x}")
    if stack is None or len(stack) == 0:
        raise ParseException("empty stack")
    if len(stack) > 1:
        raise ParseException("too many values from expression!")
    return stack[0]


class CompiledExpression:
    """A parsed expression, ready to be executed (possibly repeatedly, and with
    rebound variables - see Parser.registerVar) without re-parsing."""

    def __init__(self, instructions: List[Instruction], source: str):
        self.instructions = instructions
        self.source = source

    def execute(self, stack: Optional[Stack] = None) -> Datum:
        if stack is None:
            stack = []
        return execute(self.instructions, stack)


class Visitor(TreeVisitor):
    def __init__(self, parser: Parser):
        self.parser = parser

    def generate_number(self, data: Any) -> Any:
        return InstNumber(float(data.value))
    def generate_string(self, data: Any) -> Any:
        return InstString(data.value)
    def generate_name(self, data: Any) -> Any:
        # names are converted into variable references or bare identifiers
        # if they are not variables (so that property fetch with "." works)
        name = data.value
        if name in self.parser.varRegistry:
            return InstVar(self.parser.varRegistry[name])
        else:
            return InstIdent(data.value)
    def generate_binop(self, data: Any) -> Any:
        return InstBinop(data, self.parser)
    def generate_unop(self, data: Any) -> Any:
        return InstUnop(data, self.parser)
    def generate_apply(self, data: Any, child_count: int) -> Any:
        if data=='call':
            # Needs to lookup the function at runtime, which is annoying.
            # -1 because stacktop is the caller, which doesn't count!
            return InstCall(self.parser, child_count-1)
        elif data=='index':
            return InstIndex(child_count-1)
        else:
            raise ParseException(f"unknown application treenode type: {data}")

    def generate_vector(self, child_count:int) -> Any:
        if child_count==0:
            raise ParseException("syntax error - empty vectors not allowed")
        return InstCreateVector(child_count)



class Parser(PrattParser):
    """Expression parser using the shunting algorithm, also incorporating the virtual machine for evaluation"""

    ## binops are names (e.g. '+') mapped to a two-arg fn which returns a value
    binopRegistry: Dict[str, Callable[[Any, Any], Any]]

    def registerBinop(self, name: str, fn: Callable[[Any, Any], Any]):
        """Register a binary operation"""
        self.binopRegistry[name] = fn

    ## unary ops are names mapped to precedence and single arg function which returns a value
    unopRegistry: Dict[str, Callable[[Any], Any]]

    def registerUnop(self, name: str, fn: Callable[[Any], Any]):
        """Register a unary operation"""
        self.unopRegistry[name] = fn

    ## vars are names mapped to argless fns (wrapped in a class) which
    # return their value
    varRegistry: Dict[str, Variable]

    def registerVar(self, name: str, description: str, fn: Callable[[], Any]):
        """Register a variable with a parameterless function to fetch it. If a variable
        with this name is already registered, its function and description are updated
        in place rather than replacing the Variable object - this lets a previously
        compiled expression (see compile()) pick up the new value on its next execution
        without needing to be re-parsed, because its InstVar instructions hold a
        reference to this same Variable object."""
        if name in self.varRegistry:
            v = self.varRegistry[name]
            v.fn = fn
            v.desc = description
        else:
            self.varRegistry[name] = Variable(name, fn, description)

    ## other functions are names mapped to functions
    ## which take a list of args and return an arg
    funcRegistry: Dict[str, Function]

    def registerFunc(self, name: str,
                     description: str,
                     # this is a list of Parameter objects, one for each mandatory parameter. Default values on the parameters are ignored.
                     # if none, we don't type check at all.
                     mandatoryParams: Optional[List[Parameter]],
                     # This is a Parameter objects, one for each optional parameter, each of which should have a default.
                     optParams: List[Parameter],
                     # the actual function to call, which takes a list of mandatory arguments, a list of optional arguments,
                     # and returns a datum.
                     fn: Callable[[List[Datum], List[Datum]], Datum],
                     # if true, there are no optional arguments and all extra args must
                     # have the same type as the last mandatory argument
                     varargs=False,
                     ):
        """register a function - the callable should take a list of args, a list of optional args and return a value.
        Also takes a description and two lists of argument types: mandatory and optional."""
        # print(f"Registered func {name}")
        self.funcRegistry[name] = Function(name, fn, description, mandatoryParams, optParams, varargs)

    # property dict - keys are (name,type), values are (desc,func) where the func
    # takes Datum and gives Datum

    properties: Dict[Tuple[str, Type], Tuple[str, Callable[[Datum], Datum]]]

    def registerProperty(self, name: str, tp: Type, desc: str, func: Callable[[Datum], Datum]):
        """add a property (e.g. the 'w' in 'a.w'), given name, input type, description and function"""
        self.properties[(name, tp)] = (desc, func)

    def getProperty(self, a: Datum, b: Datum):
        """Get the value of a property - requires two Datum arguments, the first is the object and the second is
        the property name (an identifier)"""
        if a is None:
            raise ParseException('first argument is None in "." operator')
        if b is None:
            raise ParseException('second argument is None in "." operator')
        if b.tp != Datum.IDENT:
            raise ParseException('second argument should be identifier in "." operator')
        propName = b.val

        try:
            _, func = self.properties[(propName, a.tp)]
            return func(a)   # pass a Datum even though we already know the type; we might need (say) source info.
        except KeyError:
            raise ParseException('unknown property "{}" for given type in "." operator'.format(propName))

    def listProps(self, nameToFind: Optional[str] = None):
        """Generate help on properties as Markdown, or get help on a single property"""
        t = Table()
        for k, v in self.properties.items():
            name, tp = k
            desc, _ = v
            if nameToFind is None or nameToFind == name:
                t.newRow()
                t.add("name", "x." + name)
                t.add("type of x", tp.name)
                t.add("desc", desc)
        if len(t) == 0:
            return None  # no match found!
        return t.markdown()

    def helpOnWord(self, name: str):
        """Generate help on a word, which can be a property or a function."""
        if name in self.funcRegistry:
            return self.funcRegistry[name].help()
        elif name in self.varRegistry:
            return self.varRegistry[name].help()
        else:
            s = self.listProps(nameToFind=name)
            if s is not None:
                return s

        return "Function not found"

    def listFuncs(self):
        """Generate a list of all functions with help"""
        t = Table()
        for name, f in sorted(self.funcRegistry.items()):
            t.newRow()
            t.add("name", name)
            ps = ",".join([p.name for p in f.mandatoryParams])
            if f.varargs:
                ps += "..."
            t.add("params", ps)
            t.add("opt. params (default in brackets)", ",".join([f"{p.name} ({p.deflt})" for p in f.optParams]))
            # remove newlines from the description, even though it breaks the markdown
            t.add("description", " ".join(f.desc.split('\n')))
        return t.markdown()

    def __init__(self):
        """Initialise the parser, clearing all registered vars, funcs and ops."""
        super().__init__()

        # these are not the same as the registries used inside the PrattParser; those are lower level.
        # These are used during post-processing of the AST to produce PCOT-level instructions.
        self.binopRegistry = dict()
        self.unopRegistry = dict()
        self.varRegistry = dict()
        self.funcRegistry = dict()
        self.properties = dict()

        # getProperty is built into the parser. Binds before anything else.
        self.register_infix_left_associative(".", 1000)
        self.registerBinop('.', lambda a, b: self.getProperty(a, b))

    def parse(self, s: str) -> List[Instruction]:
        """Parse a string into a list of Instructions"""
        # step 1 - get the syntax tree (i.e. actually parse, but PCOT-agnostic data)
        t:TreeNode = super().parse(s)
        # step 2 - walk this tree to get the actual instructions using a TreeVisitor
        visitor = Visitor(self)
        return visitor.visit(t)



    def compile(self, s: str) -> CompiledExpression:
        """Parse an expression and return it as a standalone CompiledExpression,
        which can be executed (possibly repeatedly, and with rebound variables -
        see registerVar) without re-parsing."""
        instructions = self.parse(s)
        return CompiledExpression(list(instructions), s)