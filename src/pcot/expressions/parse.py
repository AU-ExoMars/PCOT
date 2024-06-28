"""This is the expression parser and VM, which uses a shunting-yard algorithm to
produce a sequence of instructions for a stack machine. While largely application
independent, it does use PCOT's Datum type as a variant record, and conntypes to
handle type checking. Help texts are also generated.
"""

import numbers
import logging

from io import BytesIO
from tokenize import tokenize, TokenInfo, NUMBER, NAME, OP, ENCODING, ENDMARKER, NEWLINE, ERRORTOKEN, PERCENT, DOT, \
    STRING

from typing import List, Any, Optional, Callable, Dict, Tuple, Union

from pcot.datum import Datum
from pcot.datumtypes import Type
from pcot.sources import nullSourceSet, SourceSet
from pcot.utils.table import Table
from pcot.value import Value

Stack = List[Any]

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

    def __init__(self, msg: str, t: Optional[TokenInfo] = None):
        if t is not None:
            msg = "{}: '{}' at chars {}-{}".format(msg, t.string, t.start[1], t.end[1])
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

    def __init__(self, name: str, fn: Callable[[List[Any]], Any], description: str,
                 mandatoryParams: List[Parameter], optParams: List[Parameter], varargs):
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
        lastparam = None

        if self.mandatoryParams is None:
            return args  # no type checking, just pass all args straight through

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
    name: str

    def __init__(self, var):
        self.var = var

    def exec(self, stack: Stack):
        stack.append(self.var.fn())

    def __str__(self):
        return "VAR {}".format(self.var.name)


class InstFunc(Instruction):
    """A VM instruction for stacking a function.
    Does not call the function! InstCall does that. Holds the function to be called by the VM, and the
    name of the function for debugging."""
    callback: Callable[[List[Any]], Any]
    name: str

    def __init__(self, name, func: Function):
        self.func = func
        self.name = name

    def exec(self, stack: Stack):
        """actually stack the callback function, don't call it - InstCall does that."""
        stack.append(Datum(Datum.FUNC, self.func, nullSourceSet))

    def __str__(self):
        return "FUNC {}".format(self.name)


class InstOp(Instruction):
    """A VM instruction for performing a unary (prefix) or binary operation.
    The constructor fetches the function to call from the appropriate
    registry."""
    name: str
    prefix: bool
    precedence: int

    def __init__(self, n: str, pre: bool, parser: 'Parser'):
        if pre and n in parser.unopRegistry:
            self.precedence, self.callback = parser.unopRegistry[n]
        elif not pre and n in parser.binopRegistry:
            self.precedence, self.callback = parser.binopRegistry[n]
        else:
            raise ParseException("unknown {} operator: {}".format('prefix' if pre else 'suffix', n))
        self.name = n
        self.prefix = pre

    def exec(self, stack: Stack):
        # these are written in a rather long-winded way to ease breakpointing
        if self.prefix:
            a = stack.pop()
            r = self.callback(a)
            stack.append(r)
        else:
            b = stack.pop()
            a = stack.pop()
            r = self.callback(a, b)
            stack.append(r)

    def __str__(self):
        return "OP {} {}".format(self.name, "PRE" if self.prefix else "IN")


class InstBracket(InstOp):
    """A VM instruction used internally to process brackets in the shunting yard algorithm;
    should never be output as part of the instruction stream"""

    def __init__(self, parser: 'Parser'):
        # still need the string argument so InstOp knows which precedence to look up
        super().__init__('(', False, parser)
        self.argcount = 0

    def exec(self, stack: Stack):
        raise Exception("bracket instruction should never be executed")


class InstSquareBracket(InstOp):
    """A VM instruction used internally to process square brackets in the shunting yard algorithm;
    should never be output as part of the instruction stream"""

    def __init__(self, parser: 'Parser'):
        # still need the string argument so InstOp knows which precedence to look up
        super().__init__('[', False, parser)
        self.argcount = 0

    def exec(self, stack: Stack):
        raise Exception("bracket instruction should never be executed")


class InstCall(Instruction):
    """The VM instruction which calls the function on top of the stack (see InstFunction).
    If the function wasn't registered, an ident will be stacked instead."""

    def __init__(self, argcount):
        self.argcount = argcount

    def __str__(self):
        return "CALL  argcount: {}".format(self.argcount)

    def exec(self, stack: Stack):
        """execute: pop off the args, then pop off the function value"""
        if self.argcount != 0:
            args = stack[-self.argcount:]
        else:
            args = []
        # args.reverse()   # is this faster than just popping them in reverse order?
        # this is really annoying; can't delete multiple items from the stack without slicing and
        # can't slice because that wouldn't change the original stack.
        for x in range(0, self.argcount):
            stack.pop()
        v = stack.pop()
        if v.tp == Datum.IDENT:
            raise ParseException("unknown function '{}' ".format(v.val))
        elif v.tp == Datum.FUNC:
            # this executes the function by calling it's call method,
            # which will do argument type checking.
            stack.append(v.val.call(args))
        else:
            # if we do (say) "a()", we'll get "cannot call a (whatever input A is connected to)..."
            raise ParseException("cannot call a {} as if it were a function".format(v.tp))


class InstVector(Instruction):
    """VM instruction for getting an element of a vector - e.g. vector[index]. The vector will
    be below the index on the stack"""

    def __init__(self, argcount):
        self.argcount = argcount

    def __str__(self):
        return "INSTVECTOR  argcount: {}".format(self.argcount)

    def exec(self, stack: Stack):
        """execute: pop off the args, then pop off the vector value"""
        if self.argcount != 0:
            args = stack[-self.argcount:]
        else:
            args = []
        for x in range(0, self.argcount):
            stack.pop()
        v = stack.pop()
        if v.tp == Datum.IDENT:
            raise ParseException("unknown function '{}' ".format(v.val))
        elif v.tp == Datum.NUMBER:
            if len(args) > 1:
                raise ParseException("only 1D vectors supported")
            idx = args[0]
            if idx.tp != Datum.NUMBER or not idx.val.isscalar():
                raise ParseException("indices must be scalars")
            i = idx.get(Datum.NUMBER)

            res = v.val[i.n]
            sources = SourceSet([v.sources, idx.sources])
            stack.append(Datum(Datum.NUMBER, res, sources))
        else:
            # if we do (say) "a()", we'll get "cannot call a (whatever input A is connected to)..."
            raise ParseException("cannot get a value from a {} as if it were a vector".format(v.tp))


def execute(seq: List[Instruction], stack: Stack) -> float:
    """Execute a list of instructions on a given stack"""
    for inst in seq:
        inst.exec(stack)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"EXECUTED {inst}, STACK NOW (top shown last):")
            for x in stack:
                logger.debug(f"    {x}")
    return stack[0]


def isOp(t):
    """Return whether a token is an operator (since we've got some weird ones)"""
    return t.type in [OP, ERRORTOKEN, PERCENT, DOT]


def dequote(s):
    """Remove quotes from a string if it's quoted and the quotes match"""
    if (len(s) >= 2 and s[0] == s[-1]) and s.startswith(("'", '"')):
        return s[1:-1]
    return s


class Parser:
    """Expression parser using the shunting algorithm, also incorporating the virtual machine for evaluation"""
    list: List[TokenInfo]
    output: List[Instruction]
    opstack: List[Instruction]  # compile stack

    ## if true, naked identifiers are stacked as strings.
    nakedIdents: bool

    ## binops are names (e.g. '+') mapped to precedence and two-arg fn which return a value
    binopRegistry: Dict[str, Tuple[int, Optional[Callable[[Any, Any], Any]]]]

    def registerBinop(self, name: str, precedence: int, fn: Callable[[Any, Any], Any]):
        """Register a binary operation"""
        self.binopRegistry[name] = (precedence, fn)

    ## unary ops are names mapped to precedence and single arg function which returns a value
    unopRegistry: Dict[str, Tuple[int, Optional[Callable[[Any], Any]]]]

    def registerUnop(self, name: str, precedence: int, fn: Callable[[Any], Any]):
        """Register a unary operation"""
        self.unopRegistry[name] = (precedence, fn)

    ## vars are names mapped to argless fns (wrapped in a class) which
    # return their value
    varRegistry: Dict[str, Variable]

    def registerVar(self, name: str, description: str, fn: Callable[[], Any]):
        """register a variable with a parameterless function to fetch it"""
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
            return func(a.get(a.tp))
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
            t.add("description", f.desc)
        return t.markdown()

    def out(self, inst: Instruction):
        """Internal method to output an instruction (part of shunting yard)"""
        self.output.append(inst)

    def stackOp(self, op: InstOp):
        """Internal method to put an operator onto the operator stack (part of shunting yard)"""
        self.opstack.append(op)

    def __init__(self, nakedIdents=False):
        """Initialise the parser, clearing all registered vars, funcs and ops.
        If nakedIdents are true, then identifiers which are not in the function
        or variable registries are compiled as literal strings (InstIdent) """
        self.binopRegistry = dict()
        self.unopRegistry = dict()
        self.varRegistry = dict()
        self.funcRegistry = dict()
        self.properties = dict()
        self.toks = []

        self.nakedIdents = nakedIdents

        # preregister the special operators for open bracket
        self.binopRegistry['('] = (100, None)
        self.unopRegistry['('] = (100, None)
        self.binopRegistry['['] = (100, None)
        self.unopRegistry['['] = (100, None)
        # getProperty is built into the parser, but can be bound to any operator.
        self.registerBinop('.', 80, lambda a, b: self.getProperty(a, b))

    def parse(self, s: str):
        """Parsing function - uses the shunting algorithm.
        See also
        https://stackoverflow.com/questions/16380234/handling-extra-operators-in-shunting-yard/16392115
        """
        s = s.replace('\n', '').replace('\r', '')  # remove rogue newlines
        x = BytesIO(s.encode())
        self.toks = [x for x in (tokenize(x.readline) or []) if x.type != ENCODING
                     and x.type != ENDMARKER and
                     x.type != NEWLINE]
        self.opstack = []
        self.output = []

        wantOperand = True

        while True:
            if wantOperand:
                ######### In this mode, we want an operand next. Otherwise we want an operator.
                #   read a token. If there are no more tokens, announce an error.
                t = self.next()
                if t is None:
                    raise ParseException("premature end", t)
                elif isOp(t):
                    #  if the token is an prefix operator or an open bracket:
                    #    mark it as prefix and push it onto the operator stack
                    # Note that the bracket case is different from when we meet it in the
                    # !wantOperand case. It's just a prefix op here, otherwise we'd end up
                    # generating a CALL when we don't want one.
                    if t.string in self.unopRegistry or t.string == '(' or t.string == '[':
                        self.stackOp(InstOp(t.string, True, self))
                    #  if we meet a ')' or ']' it should be a function/array with no arguments
                    #  So all the code in these two clauses only applies to [] or (). Sorry.
                    elif t.string == ']':
                        if len(self.opstack) == 0:  # we need that left bracket
                            raise ParseException("syntax error : bad no-arg function - no left bracket", t)
                        op = self.opstack.pop()
                        if isinstance(op, InstSquareBracket):
                            raise ParseException('syntax error: empty square brackets', t)
                        elif isinstance(op, InstBracket):
                            raise ParseException("syntax error : open bracket matched with close square bracket?", t)
                        else:
                            raise ParseException('syntax error: no-arg function with no name?', t)
                    elif t.string == ')':
                        if len(self.opstack) == 0:  # we need that left bracket
                            raise ParseException("syntax error : bad no-arg function - no left bracket", t)
                        op = self.opstack.pop()
                        if isinstance(op, InstBracket):
                            if not op.prefix:
                                if op.argcount != 0:
                                    raise ParseException("syntax error : bad no-arg function - has args!", t)
                                self.out(InstCall(0))
                                wantOperand = False
                        elif isinstance(op, InstSquareBracket):
                            raise ParseException("syntax error : open square bracket matched with close bracket?", t)
                        else:
                            raise ParseException('syntax error: no-arg function with no name?', t)
                #     add it to the output queue
                #     goto have_operand
                elif t.type == NUMBER:
                    self.out(InstNumber(float(t.string)))
                    wantOperand = False
                elif t.type == STRING:

                    self.out(InstString(dequote(t.string)))
                    wantOperand = False
                elif t.type == NAME:
                    if t.string in self.varRegistry:
                        self.out(InstVar(self.varRegistry[t.string]))
                    elif t.string in self.funcRegistry:
                        fn = self.funcRegistry[t.string]
                        self.out(InstFunc(t.string, fn))
                    elif self.nakedIdents:
                        self.out(InstIdent(t.string))
                    else:
                        raise ParseException("unknown variable or function", t)
                    wantOperand = False
                else:
                    #   if the token is anything else, announce an error and stop.
                    raise ParseException("weird token", t)
            else:  # wantOperand = false
                ######### In this mode, we want an operator next. Otherwise we want an operand.
                #   read a token
                t = self.next()
                #   if there are no more tokens:
                if t is None:
                    #     pop all operators off the stack, adding each one to the output queue.
                    while len(self.opstack) > 0:
                        op = self.opstack.pop()
                        #     if an open bracket is found on the stack, announce an error and stop.
                        if isinstance(op, InstOp) and op.name == '(' or op.name == '[':
                            raise ParseException("syntax error : mismatched bracket left", t)
                        self.out(op)
                    return  # ALL DONE
                #   if the token is a postfix operator:
                #   could deal with postfix here, but won't.

                # if the token is a close bracket:
                if isOp(t) and t.string == ')' or t.string == ']':
                    #     while the top of the stack is not '(' or '[':
                    while self.stackTopIsNotLPar():
                        #       pop an operator off the stack and add it to the output queue
                        op = self.opstack.pop()
                        self.out(op)
                    #     if the stack becomes empty, announce an error and stop.
                    if len(self.opstack) == 0:
                        raise ParseException("syntax error : mismatched bracket right", t)
                    #     if the '(' is marked infix, add a "call" operator to the output queue (*)
                    #     (using the arg count from the '(' )
                    op = self.opstack.pop()
                    if isinstance(op, InstSquareBracket) and t.string == ')':
                        raise ParseException("syntax error : mismatched bracket, expected ]", t)
                    if isinstance(op, InstBracket) and t.string == ']':
                        raise ParseException("syntax error : mismatched bracket, expected )", t)
                    if not op.prefix:
                        # I regret to inform you that I have no idea why I have to add 1 to the argument count
                        if isinstance(op, InstSquareBracket):
                            self.out(InstVector(op.argcount + 1))
                        elif isinstance(op, InstBracket):
                            self.out(InstCall(op.argcount + 1))
                        else:
                            raise ParseException("syntax error : mismatched bracket right 2", t)
                    #     pop the '(' off the top of the stack
                    #     goto have_operand (already there)

                elif isOp(t) and t.string == ',':
                    #   if the token is a ',':
                    #     while the top of the stack is not a '(' or '[' bracket:
                    while self.stackTopIsNotLPar():
                        #       pop an operator off the stack and add it to the output queue
                        op = self.opstack.pop()
                        self.out(op)
                    # top of stack should now be a '(' or '[', which is special - increment the argument count
                    self.opstack[-1].argcount += 1
                    #                    self.out(InstComma())  # JCF mod - add comma as actual operator with low precendence
                    #     if the stack becomes empty, announce an error
                    if len(self.opstack) == 0:
                        raise ParseException("syntax error : mismatched bracket left 2", t)
                    #     goto want_operand
                    wantOperand = True
                elif isOp(t):
                    #   if the token is an infix operator:
                    if t.string == '(':
                        op = InstBracket(self)
                    elif t.string == '[':
                        op = InstSquareBracket(self)
                    else:
                        op = InstOp(t.string, False, self)
                    while self.stackTopIsOperatorPoppable(op):
                        self.out(self.opstack.pop())
                    self.stackOp(op)
                    wantOperand = True
                else:
                    # token is probably an operand.
                    raise ParseException("syntax error : unexpected operand", t)

    def stackTopIsNotLPar(self):
        """internal method - op stack top is NOT an open bracket"""
        if len(self.opstack) == 0:
            return False
        op = self.opstack[-1]  # peek
        # must be an operator, and not a left-parenthesis
        return op.name != '(' and op.name != '['

    def stackTopIsOperatorPoppable(self, curop):
        """internal method - stack top is poppable to output"""
        if len(self.opstack) == 0:
            return False
        op = self.opstack[-1]  # peek
        # must not be a left-parenthesis
        if op.name == '(' or op.name == '[':
            return False
        # operator at stack top must have greater precedence, or the same precedence and token is left-assoc
        # (which they all are)
        return op.precedence >= curop.precedence

    def next(self) -> TokenInfo:
        """internal method - get next token"""
        if self.toksLeft():
            logger.debug(f"Next token : {self.toks[0]}")
            return self.toks.pop(0)
        else:
            return None

    def rewind(self, tok: TokenInfo):
        """tokeniser rewinder, unused."""
        self.toks.insert(0, tok)

    def peek(self) -> TokenInfo:
        """tokeniser peek, unused"""
        if self.toksLeft():
            return self.toks[0]
        else:
            return None

    def toksLeft(self) -> bool:
        """count remaining tokens"""
        return len(self.toks) > 0
