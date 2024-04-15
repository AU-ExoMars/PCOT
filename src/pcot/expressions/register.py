"""
Registration and utility functions for the expression evaluator
"""

from numbers import Number
from typing import List, Optional, Callable

import numpy as np

from pcot.config import parserhook
from pcot.datum import Datum
from pcot.expressions import Parameter
from pcot.sources import SourceSet, nullSourceSet
from pcot.value import Value
from pcot.xform import XFormException


def funcWrapper(fn: Callable[[Value], Value], d: Datum) -> Datum:
    """Takes a function which takes and returns Value, and a datum. This is a utility for dealing with
    functions. For images, it strips out the relevant pixels (subject to ROIs) and creates a masked array. However, BAD
    pixels are included. It then performs the operation and creates a new image which is a copy of the
    input with the new data spliced in."""

    if d is None:
        return None
    elif d.tp == Datum.NUMBER:  # deal with numeric argument (always returns a numeric result)
        # get sources for all arguments
        ss = d.getSources()
        rv = fn(d.val)
        return Datum(Datum.NUMBER, rv, SourceSet(ss))
    elif d.isImage():
        img = d.val
        ss = d.sources
        subimage = img.subimage()

        # make copies of the source data into which we will splice the results
        imgcopy = subimage.img.copy()
        unccopy = subimage.uncertainty.copy()
        dqcopy = subimage.dq.copy()

        # Perform the calculation on the entire subimage rectangle, but only the results covered by ROI
        # will be spliced back into the image (modifyWithSub does this).
        v = Value(imgcopy, unccopy, dqcopy)

        rv = fn(v)
        # depending on the result type..
        if rv.isscalar():
            # ...either use it as a number datum
            return Datum(Datum.NUMBER, rv, ss)
        else:
            # ...or splice it back into the image
            img = img.modifyWithSub(subimage, rv.n, uncertainty=rv.u, dqv=rv.dq)
            return Datum(Datum.IMG, img)


def statsWrapper(fn, d: List[Optional[Datum]], *args) -> Datum:
    """similar to funcWrapper, but can take lots of image and number arguments which it aggregates to do stats on.
    The result of fn must be a number. Works by flattening any images and concatenating them with any numbers,
    and doing the operation on the resulting data.

    fn takes a tuple of nominal and uncertainty values compressed into a 1D array, and returns a Value.
    """

    intermediate = None
    uncintermediate = None

    sources = []
    for x in d:
        # get each datum, which is either numeric or an image.
        if x is None:
            continue
        elif x.isImage():
            # if an image, convert to a 1D array
            subimage = x.val.subimage()
            # we ignore "bad" pixels in the data
            mask = subimage.fullmask(maskBadPixels=True)
            cp = subimage.img.copy()
            cpu = subimage.uncertainty.copy()

            sources.append(x.sources)
            masked = np.ma.masked_array(cp, mask=~mask)
            uncmasked = np.ma.masked_array(cpu, mask=~mask)

            # we convert the data into a flat numpy array if it isn't one already
            if isinstance(masked, np.ma.masked_array):
                newdata = masked.compressed()  # convert to 1d and remove masked elements
            elif isinstance(masked, np.ndarray):
                newdata = masked.flatten()  # convert to 1d
            else:
                raise XFormException('EXPR', 'internal: data in masked array is wrong type in statsWrapper')
            if isinstance(uncmasked, np.ma.masked_array):
                uncnewdata = uncmasked.compressed()  # convert to 1d and remove masked elements
            elif isinstance(uncmasked, np.ndarray):
                uncnewdata = uncmasked.flatten()  # convert to 1d
            else:
                raise XFormException('EXPR', 'internal: data in uncmasked array is wrong type in statsWrapper')

        elif x.tp == Datum.NUMBER:
            # if a number, convert to a single-value array
            newdata = np.array([x.val.n], np.float32)
            uncnewdata = np.array([x.val.u], np.float32)
            sources.append(x.sources)
        else:
            raise XFormException('EXPR', 'internal: bad type passed to statsWrapper')

        # and concat it to the intermediate array
        if intermediate is None:
            intermediate = newdata
            uncintermediate = uncnewdata
        else:
            intermediate = np.concatenate((intermediate, newdata))
            uncintermediate = np.concatenate((uncintermediate, uncnewdata))

    # then we perform the function on the collated arrays
    val = fn(intermediate, uncintermediate, *args)
    return Datum(Datum.NUMBER, val, SourceSet(sources))


@parserhook
def registerBuiltinFunctions(p):
    # register the built-in functions that have been registered through the datumfunc mechanism.
    for _, f in datumfunc.registry.items():
        p.registerFunc(f.name, f.description, f.mandatoryParams, f.optParams, f.exprfunc, varargs=f.varargs)


@parserhook
def registerBuiltinProperties(p):
    p.registerProperty('w', Datum.IMG,
                       "give the width of an image in pixels (if there are ROIs, give the width of the BB of the ROI union)",
                       lambda q: Datum(Datum.NUMBER, Value(q.subimage().bb.w, 0.0), SourceSet(q.getSources())))
    p.registerProperty('w', Datum.ROI, "give the width of an ROI in pixels",
                       lambda q: Datum(Datum.NUMBER, Value(q.bb().w, 0.0), SourceSet(q.getSources())))
    p.registerProperty('h', Datum.IMG,
                       "give the height of an image in pixels (if there are ROIs, give the width of the BB of the ROI union)",
                       lambda q: Datum(Datum.NUMBER, Value(q.subimage().bb.h, 0.0), SourceSet(q.getSources())))
    p.registerProperty('h', Datum.ROI, "give the width of an ROI in pixels",
                       lambda q: Datum(Datum.NUMBER, Value(q.bb().h, 0.0), SourceSet(q.getSources())))

    p.registerProperty('n', Datum.IMG,
                       "give the area of an image in pixels (if there are ROIs, give the number of pixels in the ROI union)",
                       lambda q: Datum(Datum.NUMBER, Value(q.subimage().mask.sum(), 0.0), SourceSet(q.getSources())))
    p.registerProperty('n', Datum.ROI, "give the number of pixels in an ROI",
                       lambda q: Datum(Datum.NUMBER, Value(q.pixels(), 0.0), SourceSet(q.getSources())))


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
                    # this must be either numeric or string.
                    # first check the default's type is string/numeric and that the acceptable type tuple
                    # has a string/numeric type in it
                    from pcot.datumtypes import NumberType, StringType
                    if NumberType.instance not in paramtypes[k] and StringType.instance not in paramtypes[k]:
                        raise ValueError(f"Function {self.name} parameter {k} is not numeric or string, and so cannot accept a default")

                    if isinstance(v.default, Number):
                        if NumberType.instance not in paramtypes[k]:
                            raise ValueError(f"Function {self.name} parameter {k} cannot have a numeric default")
                    elif isinstance(v.default, str):
                        if StringType.instance not in paramtypes[k]:
                            raise ValueError(f"Function {self.name} parameter {k} cannot have a string default")
                    else:
                        raise ValueError(f"Function {self.name} has a parameter {k} with a default which is neither a number nor a string")
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

        # and another wrapper which just runs through the arguments and converts any numeric and string types to Datum
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
                try:
                    # we're going to have to convert the default value to a Datum object. We know the default
                    # is of a valid type for this parameter, we checked during __init__. So we can just use
                    # instanceof here.
                    if isinstance(self.optParams[i].deflt, str):
                        arg = Datum(Datum.STRING, self.optParams[i].deflt, nullSourceSet)
                    else:
                        arg = Datum.k(self.optParams[i].deflt)   # assume it's numeric.
                    args += (arg,)
                except IndexError:
                    raise ValueError(f"Function {self.name} is missing arguments")

            def convert_arg(v):
                if isinstance(v, (Number, int)):
                    return Datum.k(v)
                elif isinstance(v, str):
                    return Datum(Datum.STRING, v, nullSourceSet)
                else:
                    return v

            kwargs = {kk: convert_arg(vv) for kk, vv in kwargs.items()}

            vals = [convert_arg(vv) for vv in args]

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
