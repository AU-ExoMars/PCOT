import numbers
from typing import Union, Tuple, Optional, Callable, Any, List

from pcot.datum import Datum
from pcot.datumtypes import Type
from pcot.sources import nullSourceSet
from pcot.utils.table import Table
from pcot.value import Value


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
