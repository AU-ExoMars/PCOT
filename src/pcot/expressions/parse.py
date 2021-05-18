# This is the core of the expression parsing system.
# The actual operations etc. are in eval.py.


from io import BytesIO

from tokenize import tokenize, TokenInfo, NUMBER, NAME, OP, ENCODING, ENDMARKER, NEWLINE, ERRORTOKEN, PERCENT, DOT

from typing import List, Any, Optional, Callable, Dict, Tuple

import pcot.conntypes as conntypes
from pcot.conntypes import Datum

Stack = List[Any]

# will turn on printing
debug: bool = False


class Instruction:
    """Instruction interface"""

    def exec(self, stack: Stack):
        pass


class InstNumber(Instruction):
    val: float

    def __init__(self, v: float):
        self.val = v

    def exec(self, stack: Stack):
        # can't import NUMBER, it clashes with the one in tokenizer.
        stack.append(Datum(conntypes.NUMBER, self.val))

    def __str__(self):
        return "NUM {}".format(self.val)


class InstIdent(Instruction):
    val: str

    def __init__(self, v: str):
        self.val = v

    def exec(self, stack: Stack):
        stack.append(Datum(conntypes.IDENT, self.val))

    def __str__(self):
        return "STR {}".format(self.val)


class InstVar(Instruction):
    callback: Callable[[], Any]

    def __init__(self, name, callback: Callable[[], Any]):
        self.callback = callback
        self.name = name

    def exec(self, stack: Stack):
        stack.append(self.callback())

    def __str__(self):
        return "VAR {}".format(self.name)


class InstFunc(Instruction):
    callback: Callable[[List[Any]], Any]

    def __init__(self, name, callback):
        self.callback = callback
        self.name = name

    def exec(self, stack: Stack):
        # actually stack the callback function, don't call it.
        stack.append(self.callback)

    def __str__(self):
        return "FUNC {}".format(self.name)


class InstOp(Instruction):
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
        if self.prefix:
            stack.append(self.callback(stack.pop()))
        else:
            b = stack.pop()
            a = stack.pop()
            stack.append(self.callback(a, b))

    def __str__(self):
        return "OP {} {}".format(self.name, "PRE" if self.prefix else "IN")


class InstBracket(InstOp):
    def __init__(self, parser: 'Parser'):
        # still need the string argument so InstOp knows which precedence to look up
        super().__init__('(', False, parser)
        self.argcount = 0

    def exec(self, stack: Stack):
        raise Exception("bracket instruction should never be executed")


class InstCall(Instruction):
    def __init__(self, argcount):
        self.argcount = argcount

    def __str__(self):
        return "CALL  argcount: {}".format(self.argcount)

    def exec(self, stack: Stack):
        # semantics here - pop off the args, then pop off the function name (or some other kind of ID!)
        args = stack[-self.argcount:]
        # args.reverse()   # is this faster than just popping them in reverse order?
        # this is really annoying; can't delete multiple items from the stack without slicing and
        # can't slice because that wouldn't change the original stack.
        for x in range(0, self.argcount):
            stack.pop()
        func = stack.pop()
        if isinstance(func, str):
            raise ParseException("unknown function '{}' ".format(func))
        stack.append(func(args))


class ParseException(Exception):
    def __init__(self, msg: str, t: Optional[TokenInfo] = None):
        if t is not None:
            msg = "{}: '{}' at chars {}-{}".format(msg, t.string, t.start[1], t.end[1])
        super().__init__(msg)


def execute(seq: List[Instruction], stack: Stack) -> float:
    for inst in seq:
        inst.exec(stack)
        if debug:
            print("EXECUTED {}, STACK NOW:".format(inst))
            for x in stack:
                print(x)
    return stack[0]


def isOp(t):
    return t.type in [OP, ERRORTOKEN, PERCENT, DOT]


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

    ## vars are names mapped to argless fns which return a value
    varRegistry: Dict[str, Callable[[], Any]]

    def registerVar(self, name: str, fn: Callable[[], Any]):
        """register a variable with a function to fetch it"""
        self.varRegistry[name] = fn

    ## other functions are names mapped to functions
    ## which take a list of args and return an arg
    funcRegistry: Dict[str, Callable[[List[Any]], Any]]

    def registerFunc(self, name: str, fn: Callable[[List[Any]], Any]):
        """register a function - the callable should take a list of args and return a value"""
        self.funcRegistry[name] = fn

    def out(self, inst: Instruction):
        # internal method - output
        self.output.append(inst)

    def stackOp(self, op: InstOp):
        # internal method - stack operator
        self.opstack.append(op)

    def __init__(self, nakedIdents=False):
        """Initialise the parser, clearing all registered vars, funcs and ops."""
        self.binopRegistry = dict()
        self.unopRegistry = dict()
        self.varRegistry = dict()
        self.funcRegistry = dict()
        self.toks = []

        self.nakedIdents = nakedIdents

        # preregister the special operators for open bracket
        self.binopRegistry['('] = (100, None)
        self.unopRegistry['('] = (100, None)

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
                    #  if the token is an prefix operator or an '(':
                    #    mark it as prefix and push it onto the operator stack
                    # Note that the bracket case is different from when we meet it in the
                    # !wantOperand case. It's just a prefix op here, otherwise we'd end up
                    # generating a CALL when we don't want one.
                    if t.string == '-' or t.string == '(':
                        self.stackOp(InstOp(t.string, True, self))
                        #     goto want_operand (we just loop)
                    elif t.string == ')':
                        #     if we meet a ')' it should be a function with no arguments
                        if len(self.opstack) == 0:  # we need that left bracket
                            raise ParseException("syntax error : bad no-arg function - no left bracket", t)
                        op = self.opstack.pop()
                        if isinstance(op, InstBracket) and not op.prefix:
                            if op.argcount != 0:
                                raise ParseException("syntax error : bad no-arg function - has args!", t)
                            self.out(InstCall(0))
                            wantOperand = False
                        else:
                            raise ParseException("syntax error : no arg-func with no name? ", t)
                #   if the token is an operand (identifier or variable):
                #     add it to the output queue
                #     goto have_operand
                elif t.type == NUMBER:
                    self.out(InstNumber(float(t.string)))
                    wantOperand = False
                elif t.type == NAME:
                    if t.string in self.varRegistry:
                        self.out(InstVar(t.string, self.varRegistry[t.string]))
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
                        #     if a `(` is found on the stack, announce an error and stop.
                        if isinstance(op, InstOp) and op.name == '(':
                            raise ParseException("syntax error : mismatched bracket left", t)
                        self.out(op)
                    return  # ALL DONE
                #   if the token is a postfix operator:
                #   could deal with postfix here, but won't.

                # if the token is a ')':
                if isOp(t) and t.string == ')':
                    #     while the top of the stack is not '(':
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
                    if not op.prefix:
                        if not isinstance(op, InstBracket):
                            raise ParseException("syntax error : mismatched bracket right 2", t)
                        self.out(InstCall(op.argcount + 1))
                    #     pop the '(' off the top of the stack
                    #     goto have_operand (already there)

                elif isOp(t) and t.string == ',':
                    #   if the token is a ',':
                    #     while the top of the stack is not '(':
                    while self.stackTopIsNotLPar():
                        #       pop an operator off the stack and add it to the output queue
                        op = self.opstack.pop()
                        self.out(op)
                    # top of stack should now be a '(', which is special - increment the argument count
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
        # internal method - stack top is NOT an open bracket
        if len(self.opstack) == 0:
            return False
        op = self.opstack[-1]  # peek
        # must be an operator, and not a left-parenthesis
        return op.name != '('

    def stackTopIsOperatorPoppable(self, curop):
        # internal method - stack top is poppable to output
        if len(self.opstack) == 0:
            return False
        op = self.opstack[-1]  # peek
        # must not be a left-parenthesis
        if op.name == '(':
            return False
        # operator at stack top must have greater precedence, or the same precedence and token is left-assoc
        # (which they all are)
        return op.precedence >= curop.precedence

    def next(self) -> TokenInfo:
        # internal method - get next token
        if self.toksLeft():
            if debug:
                print(self.toks[0])
            return self.toks.pop(0)
        else:
            return None

    def rewind(self, tok: TokenInfo):
        # rewinder, unused.
        self.toks.insert(0, tok)

    def peek(self) -> TokenInfo:
        # stack peek
        if self.toksLeft():
            return self.toks[0]
        else:
            return None

    def toksLeft(self) -> bool:
        # count remaining tokens
        return len(self.toks) > 0
