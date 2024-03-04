from typing import Any, List, Callable, Optional

import pcot.datum


class datumfunc:
    """This is a decorator for functions which are to be registered as expression functions.
    The function must take a list of mandatory arguments and a list of optional arguments, and return a Datum.
    The function is registered under the name given in the first argument.

    We still need this decorator, because parameters are more complex in the expression evaluator than in
    the direct interface.
    """

    registry = {}

    name: str
    description: str
    mandatoryParams: List['Parameter']
    optParams: List['Parameter']
    varargs: bool

    def __init__(self,
                 desc: str,
                 mandatoryParams: List['Parameter'],
                 optParams: Optional[List['Parameter']] = None,
                 varargs: bool=False):
        self.description = desc
        self.mandatoryParams = mandatoryParams
        self.optParams = optParams if optParams is not None else []
        self.varargs = varargs
        # TODO this code ends up being duplicated in the Function ctor.
        if self.varargs and len(self.mandatoryParams) == 0:
            raise Exception("cannot have a function with varargs but no mandatory arguments")
        elif self.varargs and len(self.optParams) > 0:
            raise Exception("cannot have a function with varargs and optional arguments")

    def __call__(self, func: Callable[[List[Any], List[Any]], Any]):
        """This actually decorates the function, while the constructor just sets up this object
        which is used to store data about the function and register it.

        This method - the decorator proper - does two things.

        1. It stores the function pointer in the registry object
        2. It returns a wrapper to the passed in function, which is the actual function that will be called
        in a "normal" Python call.
        """
        # store our data in the registry along with the function name and the function pointer
        self.name = func.__name__
        self.registry[self.name] = self
        self.func = func

        def wrapper(*args, **kwargs):
            # we need to extract the args into a list of Datum objects. If there are too many args, we move
            # the excess into the optional list. If the optional list isn't long enough, we pad it with None.
            ct = len(self.mandatoryParams)
            from pcot.datum import Datum
            mandatory = [Datum.convert2datum(x) for x in args[:ct]]
            # if there aren't enough mandatory arguments, we raise an error
            if len(mandatory) < ct:
                raise ValueError(f"Function {self.name} requires at least {ct} arguments")
            # now we handle varargs, which just get appended to the mandatory list
            if self.varargs:
                mandatory += [Datum.convert2datum(x) for x in args[ct:]]
                optional = []
            else:
                # if there are no varargs, we can process optional args
                optional = [Datum.convert2datum(x) for x in args[ct:]]
                optional += [None] * (len(self.optParams) - len(optional))
            # we can now call the original function with the Datum objects
            return self.func(mandatory, optional)
        return wrapper

    @classmethod
    def get(cls, name):
        """get a function from the registry by name"""
        return cls.registry.get(name)


class datumfunc2:
    name: str
    description: str
    varargs: bool
    optParams: List['Parameter']
    mandatoryParams: List['Parameter']
    retType: 'Type'
    pyfunc: Callable        # function callable from Python
    exprfunc: Callable      # function callable from an expression evaluator

    registry = {}

    def __init__(self, func):
        """Extract the signature of the function and register it, under a wrapper which will convert
        the arguments to Datum objects and return a Datum object. This can then be used in an expr node.
        Then return the original function."""
        import inspect
        from pcot.expressions import Parameter
        from pcot.datum import Datum

        # get the signature of the function
        self.name = func.__name__
        sig = inspect.signature(func)

        # get the docstring; we'll get the function and parameter descriptions from this
        docstring = func.__doc__
        if docstring is None:
            raise ValueError(f"Function {self.name} has no description")
        paramdescs = {}  # dict of name: desc

        # first get the main function description. This will be the first part of the docstring,
        # up to the first @param line.
        if "@param" in docstring:
            descs = docstring.split("@param")
            # remove leading and trailing whitespace from lines in the description
            self.description = "\n".join([x.strip() for x in descs[0]])
            # now we can parse the parameter descriptions
            for d in descs[1:]:
                # split the parameter description into two parts - the parameter name and the description
                parts = d.strip().split(" ", 1)
                if len(parts) != 2:
                    raise ValueError(f"Function {self.name} has a malformed parameter description")
                paramname = parts[0].strip()
                paramdesc = parts[1].strip()
                paramdescs[paramname] = paramdesc
        else:
            # if there are no @param lines, then the whole docstring is the function description
            self.description = docstring

        # get the return type
        retType = Datum.getTypeFromPythonType(sig.return_annotation)

        # construct the two lists of Parameters - mandatory and optional. Firstly, if the only
        # parameter is *args, that's a 'varargs' function and we ignore anything else (we later
        # check for *args type parameters elsewhere in the list; they aren't valid).

        self.mandatoryParams = []
        self.optParams = []
        if len(sig.parameters) == 1 and list(sig.parameters.values())[0].kind == inspect.Parameter.VAR_POSITIONAL:
            self.varargs = True
        else:
            self.varargs = False
            for k, v in sig.parameters.items():
                desc = "DESC"
                if v.kind == inspect.Parameter.VAR_POSITIONAL:
                    raise ValueError(f"Function {self.name} has *args (or *something) in the wrong place")

                # get the type
                if v.annotation == inspect.Parameter.empty:
                    raise ValueError(f"Function {self.name} has a parameter {k} with no type")
                t = Datum.getTypeFromPythonType(v.annotation)

                # check the description is present
                if k not in paramdescs:
                    raise ValueError(f"Function {self.name} has a parameter {k} with no description")

                if v.default == inspect.Parameter.empty:
                    # we have a mandatory parameter, so we add it to the mandatory list but first we need to
                    # process the type.
                    self.mandatoryParams.append(Parameter(k, paramdescs[k], t))
                else:
                    # first check the default's type is the same as the type and is numeric
                    if Datum.getTypeFromPythonType(type(v.default)) != t:
                        raise ValueError(f"Function {self.name} has a parameter {k} with a default of the wrong type")
                    from numbers import Number
                    if not isinstance(v.default, Number):
                        raise ValueError(f"Function {self.name} has a parameter {k} with a default which is not a number")
                    self.optParams.append(Parameter(k, paramdescs[k], t, v.default))

        # now we need to create a wrapper function which will convert the arguments to Datum objects and
        # return a Datum object. This can then be used in an expr node.

        def wrapper(mandatory: List[Datum], optional: List[Datum]) -> Datum:
            # if the function is varargs, we just pass the arguments - which must be Datum already - to the
            # original function.
            if self.varargs:
                vals = mandatory
            else:
                # we need to convert each argument from a Datum to the correct Python type.
                # However, the parameter object contains *possible* types. We kow there's just
                # one, so we do the next(iter(x)) thing to get the only item from that set.
                if len(mandatory) != len(self.mandatoryParams):
                    raise ValueError(f"Function {self.name} requires {len(self.mandatoryParams)} mandatory arguments")
                vals = [m.get(next(iter(p.types))) for m, p in zip(mandatory, self.mandatoryParams)]
                # if there are too many optional arguments, we raise an error
                if len(optional) > len(self.optParams):
                    raise ValueError(f"Function {self.name} has too many optional arguments")
                # now we need to handle the optional arguments, each of which will have a default. This
                # will handle those that are present:
                vals += [o.get(next(iter(p.types))) for o, p in zip(optional, self.optParams)]
                # those that are missing will be padded with the default value
                for i in range(len(optional), len(self.optParams)):
                    vals.append(self.optParams[i].default)

            # now we can call the original function with the python objects
            rv = func(*vals)
            # and encode the returned python object as a Datum
            rv = Datum.convert2datum(rv)
            return rv

        # store both the original pythonic function and our wrapped version.
        self.pyfunc = func
        self.exprfunc = wrapper
        self.registry[self.name] = self

    def __call__(self, *args):
        self.pyfunc(*args)
