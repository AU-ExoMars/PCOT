from typing import Any, List, Callable, Optional
from numbers import Number


class datumfunc:
    """
    Decorate a function to be a "datum function" - these are functions which operate on Datum objects and can be
    called from the expression evaluator or directly from Python. The function must have a docstring which describes
    the function and its parameters. The docstring should start with a description of the function, then have a series
    of @param lines, one for each parameter. The @param line should be in the form:
        @param name: types: description
    where "types" is a comma-separated list of Datum type names indicating which Datum types the function will
    accept. The most common are "img" and "number" but there are others.

    If a function's signature contains *args, it will be treated as a varargs function. The args argument will
    consume all remaining arguments, which must have the same type as the first parameter. This cannot be the
    first parameter.


    Keyword arguments are accepted, but must be numeric.

    When a function is called directly from Python, any numeric arguments will be converted to Datum objects
    with null sources.
    """

    registry = {}       # registry of function objects - ExpressionEvaluator initialises from this.

    name: str
    description: str
    varargs: bool       # if this is true, the function takes a variable number of arguments and the next three lists are ignored
    mandatoryParams: List['Parameter']
    optParams: List['Parameter']
    paramTypes: List['Type']

    pyfunc: Callable        # function callable from Python
    exprfunc: Callable      # function callable from an expression evaluator

    def __init__(self, func):
        import inspect
        from pcot.expressions import Parameter
        from pcot.datum import Datum

        # get the docstring; we'll get the function and parameter descriptions from this
        docstring = func.__doc__
        if docstring is None:
            raise ValueError(f"Function {self.name} has no description")
        paramdescs = {}  # dict of name: desc
        paramtypes = {}  # dict of name: Datum type obj

        # first get the main function description. This will be the first part of the docstring,
        # up to the first @param line.
        if "@param" in docstring:
            descs = docstring.split("@param")
            # remove leading and trailing whitespace from lines in the description, and then remove
            # all line breaks (because this will be turned into a Markdown table cell)
            self.description = " ".join([x.strip() for x in descs[0].split('\n')])
            # now we can parse the parameter descriptions
            for d in descs[1:]:
                # split the parameter description into three parts - the parameter name,
                # the parameter Datum type name, and the description
                parts = d.strip().split(":", 2)
                if len(parts) != 3:
                    raise ValueError(f"Function {self.name} has a malformed parameter description")
                paramname = parts[0].strip()
                paramtype = parts[1].strip()
                paramdesc = parts[2].strip()
                paramdescs[paramname] = paramdesc
                try:
                    # there can be more than one type accepted, so we need to split the type name
                    # into a list of types. It's separated by commas.
                    from pcot.datumtypes import typesByName
                    paramtypes[paramname] = tuple([typesByName[x] for x in paramtype.split(",")])
                except KeyError:
                    raise ValueError(f"Function {self.name} has a parameter {paramname} with an unknown type {paramtype}")
        else:
            # if there are no @param lines, then the whole docstring is the function description
            self.description = docstring

        # now get the signature of the function
        self.name = func.__name__
        sig = inspect.signature(func)

        # construct the two lists of Parameters - mandatory and optional. Firstly, if the only
        # parameter is *args, that's a 'varargs' function and we ignore anything else (we later
        # check for *args type parameters elsewhere in the list; they aren't valid).

        self.mandatoryParams = []
        self.optParams = []
        self.varargs = False
        if len(sig.parameters) > 0 and list(sig.parameters.values())[0].kind == inspect.Parameter.VAR_POSITIONAL:
            raise ValueError(f"Function {self.name} is varargs but must have at least one non-varargs parameter")
        else:
            for k, v in sig.parameters.items():
                if v.kind == inspect.Parameter.VAR_POSITIONAL:
                    # if we get a varargs parameter, we just set the varargs flag and break out of the loop
                    self.varargs = True
                    break
                # check the description is present
                if k not in paramdescs:
                    raise ValueError(f"Function {self.name} has a parameter {k} with no description")

                if v.default == inspect.Parameter.empty:
                    # we have a mandatory parameter, so we add it to the mandatory list along with
                    # the type and description.
                    self.mandatoryParams.append(Parameter(k, paramdescs[k], paramtypes[k]))
                else:
                    # this is an optional parameter with a default value -
                    # first check the default's type is numeric and that the acceptable type tuple
                    # has a numeric type in it
                    from pcot.datumtypes import NumberType
                    if NumberType.instance not in paramtypes[k]:
                        raise ValueError(f"Function {self.name} parameter {k} cannot accept a numeric default")
                    if not isinstance(v.default, Number):
                        raise ValueError(f"Function {self.name} has a parameter {k} with a default which is not a number")
                    self.optParams.append(Parameter(k, paramdescs[k], paramtypes[k], v.default))

                # make and store a list of types
                self.paramTypes = [x for x in paramtypes.values()]

        # now we need to create a wrapper function which will convert two lists (mandatory and optional args)
        # into a single list of Datum which the passed-in function expects.

        def exprwrapper(mandatory: List[Datum], optional: List[Datum]) -> Datum:
            # if the function is varargs, we just pass the arguments - which must be Datum already - to the
            # original function.
            if self.varargs:
                vals = mandatory
            else:
                # otherwise we need to concatenate the optional and mandatory arguments into a single list.
                # We don't really need to check the types, because the expression parser will do that when
                # we call.
                vals = mandatory + optional
            # now we can call the original function
            rv = func(*vals)
            return rv

        # and another wrapper which just runs through the arguments and converts any numeric types to Datum
        # objects, then calls the original function.
        def pywrapper(*args, **kwargs):
            # First, we need to deal with the case where the function is called with missing optional
            # arguments. These are specified unwrapped in the signature, so we need to add them to the
            # actual arguments as wrapped Datums.

            # first thing - how many need to be provided? This will be the total number of arguments
            # (mandatory and optional) minus the number of arguments provided by the caller.

            totArgsRequired = len(self.mandatoryParams) + len(self.optParams)
            totArgsProvided = len(args) + len(kwargs)       # we'll assume that all the kwargs are correct..
            # the difference will be the number of arguments we need to provide to args, so defaults aren't used.
            numMissing = totArgsRequired - totArgsProvided
            # now we need to add the missing arguments to the args list.
            for i in range(numMissing):
                args += (Datum.k(self.optParams[i].deflt),)   # assume it's numeric.

            kwargs = {k: Datum.k(v) if isinstance(v, Number) else v for k, v in kwargs.items()}
            vals = [Datum.k(x) if isinstance(x, (int, Number)) else x for x in args]

            for x in vals+list(kwargs.values()):
                if not isinstance(x, Datum):
                    raise ValueError(f"Function {self.name} has a non-Datum argument")

            # in the ExpressionEvaluator, Function knows how to check arguments for validity.
            # We're not using that mechanism, so we have to do it here. We don't do this at all
            # for varargs.
            if not self.varargs:
                for i, x in enumerate(zip(vals, self.paramTypes)):
                    # is the type of the argument in the list of acceptable types?
                    if x[0].tp not in x[1]:
                        from pcot.expressions.parse import ArgsException
                        raise ArgsException(f"Function {self.name} parameter {i} is of the wrong type")

            return func(*vals, **kwargs)

        # store the funcs and register the function
        self.exprfunc = exprwrapper
        self.pyfunc = pywrapper
        self.registry[self.name] = self

    def __call__(self, *args, **kwargs):
        return self.pyfunc(*args, **kwargs)

