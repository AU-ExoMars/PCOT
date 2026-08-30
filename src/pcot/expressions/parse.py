"""This is the expression parser and VM. Parsing is done by the Pratt parser in
prattparser.py, which produces a generic syntax tree; that tree is then walked
(see Visitor) to produce a sequence of instructions for a stack machine. While
largely application independent, it does use PCOT's Datum type as a variant
record, and conntypes to handle type checking. Help texts are also generated.
"""
from __future__ import annotations

import numbers
import logging

from typing import List, Any, Optional, Callable, Dict, Tuple, Union

from pcot.datum import Datum
from pcot.datumtypes import Type
from pcot.expressions.prattparser import PrattParser, TreeVisitor, TreeNode
from pcot.sources import nullSourceSet, SourceSet
from pcot.utils.table import Table
from pcot.value import Value

Stack = List[Datum]

logger = logging.getLogger(__name__)

class ArgsException(Exception):
    """Exception indicating an error has occurred while processing an argument"""
    ## @var message
    # a string message
    message: str

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ParamException(Exception):
    """Internal exception used during parameter processing; propagated to ArgsException"""
    ## @var message
    # a string message
    message: str

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ParseException(Exception):
    """A generic error in the parser"""

    def __init__(self, msg: str = None):
        super().__init__(msg)


class Parameter:
    """a definition of a function parameter"""

    def __init__(self,
                 name: str,  # name
                 desc: str,  # description
                 types: Union[Type, Tuple[Type, ...]],  # tuple of valid types, or just one
                 deflt: Optional[numbers.Number] = None  # default value for optional parameters, must be numeric
                 ):
        self.name = name
        if isinstance(types, Type):
            types = (types,)  # convert single type to tuple
        self.types = set(types)  # convert tuple to set
        self.desc = desc
        self.deflt = deflt

    def isValid(self, datum: Datum):
        """Make sure that the datum has a type, and that this type is acceptable (is in this parameter's
        set of valid types"""
        if Datum.ANY in self.types:   # If we can return any type, all is well
            return True
        if datum is None:
            raise ParamException("None is not a valid parameter type")
        return datum.tp in self.types

    def getDefault(self):
        """Return the default value of this parameter if there is one (must be numeric)"""
        if self.deflt is None:
            raise ParamException("internal: optional parameter {} has a no default".format(self.name))
        return self.deflt

    def validArgsString(self):
        """turn a tuple (1,2,3) into "1, 2 or 3"""
        if len(self.types) == 1:
            r = str(next(iter(self.types)))  # weird idiom for "get only item from set/list"
        else:
            lst = list(self.types)
            last = lst.pop()
            r = "{} or {}".format(", ".join([str(x) for x in lst]), last)
        return r


class Variable:
    """defines a variable, which is a wrapper around a parameterless function and a description"""

    def __init__(self, name: str, fn: Callable[[], Any], desc: str):
        self.desc = desc
        self.fn = fn
        self.name = name

    def help(self):
        """return help markdown"""
        return self.desc


class Function:
    """defines a function callable from an eval string; is called from registerFunc."""

    def __init__(self, name: str, fn: Callable[[List[Datum], List[Datum]], Datum], description: str,
                 mandatoryParams: Optional[List[Parameter]], optParams: List[Parameter], varargs):
        self.fn = fn
        self.name = name
        self.desc = description
        self.mandatoryParams = mandatoryParams
        self.optParams = optParams
        self.varargs = varargs
        if self.varargs and len(self.optParams) > 0:
            raise ArgsException("cannot have a function with varargs and optional arguments")

    def help(self):
        """generate help text using the Table class, returning Markdown."""
        s = f"{self.desc}"

        if len(self.mandatoryParams) > 0:
            t = Table()
            for x in self.mandatoryParams:
                t.newRow()
                t.add("name", x.name)
                t.add("types", x.validArgsString() + ("" if not self.varargs else "..."))
                t.add("description", x.desc)
            margs = t.markdown()
            s += f"\n\n## Mandatory arguments\n\n{margs}"
        t = Table()
        if len(self.optParams) > 0:
            for x in self.optParams:
                t.newRow()
                t.add("name", x.name)
                t.add("types", x.validArgsString())
                t.add("description", x.desc)
                t.add("default", x.deflt)
            oargs = t.markdown()
            s += f"\n\n## Optional arguments\n\n{oargs}"
        return s

    def chkargs(self, args: List[Optional[Datum]]):
        """Process arguments, returning a pair of lists of Datum items: mandatory and optional args."""
        mandatArgs = []
        optArgs = []

        if self.mandatoryParams is None:
            return args, []  # no type checking, just pass all args straight through

        try:
            # consume the mandatory arguments, popping them off the front of the list
            # and checking that they are of the correct type. Each is then appended to
            # the mandatArgs list.
            for t in self.mandatoryParams:
                if len(args) == 0:
                    raise ArgsException('Not enough arguments in {}'.format(self.name))
                x = args.pop(0)
                if x is None:
                    raise ArgsException('None argument in {}'.format(self.name))
                elif t.isValid(x):
                    mandatArgs.append(x)
                else:
                    raise ArgsException(
                        'Bad argument in {}, got {}, expected {}'.format(self.name, x.tp, t.validArgsString()))
                lastparam = t

            # if we have varargs, consume all remaining arguments, no type checks(!)

            if self.varargs:
                # varargs flag set - consume remaining args
                while len(args) > 0:
                    x = args.pop(0)
                    mandatArgs.append(x)

            # mandatory and varargs have now been processed - note that varargs and optional args are
            # not compatible with each other; if we have varargs, we can't have optional args - all arguments
            # will have been consumed by this point.

            for t in self.optParams:
                # process the next optional argument
                if len(args) == 0:
                    # there are no arguments left, so we need to use the default value
                    deflt = t.getDefault()
                    if isinstance(deflt, numbers.Number):
                        optArgs.append(Datum(Datum.NUMBER, Value(deflt, 0.0), nullSourceSet))
                    elif isinstance(deflt, str):
                        optArgs.append(Datum(Datum.STRING, deflt, nullSourceSet))
                    else:
                        raise ArgsException("Internal error: parameter defaults should be numeric or string")
                else:
                    x = args.pop(0)
                    if x is None:
                        raise ArgsException('None argument in {}'.format(self.name))
                    elif t.isValid(x):
                        optArgs.append(x)
                    else:
                        raise ArgsException(
                            'Bad argument in {}, got {}, expected {}'.format(self.name, x.tp, t.validArgsString()))
        except ParamException as e:
            # propagate parameter exception adding the name
            raise ArgsException("{}: {}".format(self.name, e.message))

        if len(args)>0:
            raise ArgsException("Too many arguments in {}".format(self.name))
        return mandatArgs, optArgs

    def call(self, args):
        """do type checking for arguments, then call this function.
        Note that we pass mandatory and optional arguments"""
        args, optargs = self.chkargs(args)
        r = self.fn(args, optargs)
        # return the result, or Datum.null if the returned value is None
        return r if r is not None else Datum.null


class Instruction:
    """Interface for all instructions in the virtual machine"""

    def exec(self, stack: Stack):
        pass


class InstNumber(Instruction):
    """A VM instruction for stacking a number without uncertainty"""
    val: float

    def __init__(self, v: float):
        self.val = v

    def exec(self, stack: Stack):
        stack.append(Datum(Datum.NUMBER, Value(self.val, 0.0), nullSourceSet))

    def __str__(self):
        return "NUM {}".format(self.val)


class InstIdent(Instruction):
    """A VM instruction for stacking an identifier (a short string)"""
    val: str

    def __init__(self, v: str):
        self.val = v

    def exec(self, stack: Stack):
        stack.append(Datum(Datum.IDENT, self.val, nullSourceSet))

    def __str__(self):
        return "IDENT {}".format(self.val)


class InstString(Instruction):
    """A VM instruction for stacking a string"""
    val: str

    def __init__(self, v: str):
        self.val = v

    def exec(self, stack: Stack):
        stack.append(Datum(Datum.STRING, self.val, nullSourceSet))

    def __str__(self):
        return "STR {}".format(self.val)


class InstVar(Instruction):
    """A VM instruction for stacking a variable.
    This encapsulates a function which should be called by the VM to get the variable's value."""
    var: Variable

    def __init__(self, var):
        self.var = var

    def exec(self, stack: Stack):
        stack.append(self.var.fn())

    def __str__(self):
        return "VAR {}".format(self.var.name)


class InstUnop(Instruction):
    """A VM instruction for performing a unary (prefix) operation.
    The constructor fetches the function to call from the unop registry."""
    name: str
    callback: Callable[[Any], Any]

    def __init__(self, n: str, parser: 'Parser'):
        if n not in parser.unopRegistry:
            raise ParseException("unknown prefix operator: {}".format(n))
        self.callback = parser.unopRegistry[n]
        self.name = n

    def exec(self, stack: Stack):
        a = stack.pop()
        r = self.callback(a)
        stack.append(r)

    def __str__(self):
        return "OP {} PRE".format(self.name)


class InstBinop(Instruction):
    """A VM instruction for performing a binary (infix) operation.
    The constructor fetches the function to call from the binop registry."""
    name: str
    callback: Callable[[Any, Any], Any]

    def __init__(self, n: str, parser: 'Parser'):
        if n not in parser.binopRegistry:
            raise ParseException("unknown suffix operator: {}".format(n))
        self.callback = parser.binopRegistry[n]
        self.name = n

    def exec(self, stack: Stack):
        b = stack.pop()
        a = stack.pop()
        r = self.callback(a, b)
        stack.append(r)

    def __str__(self):
        return "OP {} IN".format(self.name)


class InstCall(Instruction):
    """Stack is arg0,arg1,arg2,func. Caller at top, and it's typically
    a function name as an ident."""

    def __init__(self, parser: Parser, argcount):
        self.parser = parser    # need this for func lookup at runtime
        self.argcount = argcount

    def __str__(self):
        return "CALL  argcount: {}".format(self.argcount)

    def exec(self, stack: Stack):
        """execute: pop off the func, then the args."""
        functok = stack.pop()
        if self.argcount != 0:
            args = stack[-self.argcount:]
            del stack[-self.argcount:]
        else:
            args = []
        # args.reverse()   # is this faster than just popping them in reverse order?

        if functok.tp == Datum.IDENT:
            func = self.parser.funcRegistry.get(functok.val)
            if func is None:
                raise ParseException("unknown function '{}' ".format(functok.val))
            stack.append(func.call(args))
        elif functok.tp == Datum.FUNC:
            # this executes the function by calling its call method,
            # which will do argument type checking.
            stack.append(functok.val.call(args))
        else:
            # if we do (say) "a()", we'll get "cannot call a (whatever input A is connected to)..."
            raise ParseException("cannot call a {} as if it were a function".format(functok.tp))


class InstCreateVector(Instruction):
    """Instruction for generating a vector. The argument count is how many items we need to pop; how
    many items will be in the vector."""
    def __init__(self, argcount):
        self.argcount = argcount

    def __str__(self):
        return "INSTCREATEVECTOR  argcount: {}".format(self.argcount)

    def exec(self, stack: Stack):
        """execute: pop off the args, then create a new vector"""
        if self.argcount != 0:
            args = stack[-self.argcount:]
            del stack[-self.argcount:]
        else:
            args = []

        sources = SourceSet()
        for x in args:
            sources.add(x.getSources())

        args = [x.get(Datum.NUMBER) for x in args]

        if any([x is None for x in args]):
            raise ParseException("only numbers can be in a vector")

        if any([not x.isscalar() for x in args]):
            raise ParseException("only scalars can be in a vector")

        # now make the vector
        n = [v.n for v in args]
        u = [v.u for v in args]
        d = [v.dq for v in args]
        stack.append(Datum(Datum.NUMBER, Value(n, u, d), sources))


class InstIndex(Instruction):
    """VM instruction for getting an element of a vector - e.g. vector[index]. The vector will
    be below the index on the stack"""

    def __init__(self, argcount):
        self.argcount = argcount

    def __str__(self):
        return "INSTINDEX  argcount: {}".format(self.argcount)

    def exec(self, stack: Stack):
        """execute: pop off vector, then args"""
        v = stack.pop()
        if self.argcount != 0:
            args = stack[-self.argcount:]
        else:
            args = []
        for x in range(0, self.argcount):
            stack.pop()

        # the type should know how to do this.
        r = v.tp.getByIndices(v, args)
        stack.append(r)

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