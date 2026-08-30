from typing import List, Callable, Any

from pcot.datum import Datum
from pcot.expressions.types import ParseException, Variable
from pcot.sources import nullSourceSet, SourceSet
from pcot.value import Value

Stack = List[Datum]

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

    def __init__(self, parser: 'Parser', argcount):
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

