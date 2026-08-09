"""This deals with the different types of connections between xforms.
To add a new type, you need to add the type's brush
(for drawing) to the brushDict here, and you may also need to
add to isCompatibleConnection if you're doing something odd.
Note that types which start with "img" are image types, and
should all be renderable by Canvas.
These types are also used by the expression evaluator.
"""
import builtins
import logging
from typing import Any, Optional

import numpy as np

from pcot.dq import NOUNCERTAINTY, NODATA, BAD
from pcot.sources import SourcesObtainable, nullSource, nullSourceSet
import pcot.datumtypes

from pcot.datumexceptions import *
from pcot.utils.maths import pooled_sd, minmax

logger = logging.getLogger(__name__)


def func_wrapper(fn, d):
    """Takes a function which takes and and returns Value, and a datum.
    Converts the datum into a Value if it's possible, passes it to the function, wraps the return value in a Datum.

    This is a utility for dealing with
    functions. For images, it strips out the relevant pixels (subject to ROIs) and creates a masked array. However, BAD
    pixels are included. It then performs the operation and creates a new image which is a copy of the
    input with the new data spliced in."""

    from pcot.value import Value
    from pcot.sources import SourceSet
    from pcot.xform import XFormException

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
    else:
        raise XFormException('EXPR', 'unsupported type for function')


def stats_wrapper(val, func):
    """Takes a function that operates on a tuple of (nominal,unc,dq) arrays for the "good" (non-BAD)
    elements under consideration and returns a tuple of the same kind for the aggregate result.

    Elements with a 'BAD' DQ bit (NODATA, SAT, DIVZERO, UNDEF, COMPLEX, ERROR) are excluded from
    the arithmetic before "func" is called. Regardless of "func"'s return value, the result's DQ
    bits are then OR'd with the DQ bits of every element that was under consideration - whether it
    ended up included in the arithmetic or excluded as BAD - so e.g. a BAD element anywhere in the
    input will always leave its mark on the result, and NODATA is forced on if every element was
    excluded (there's nothing to aggregate). See "DQ propagation in aggregate functions" in
    devguide/values.md for the reasoning.
    """

    from pcot.value import Value
    from pcot.utils.image import imgsplit
    from pcot.xform import XFormException

    def safe_func(n, u, d):
        n = np.atleast_1d(n)
        u = np.atleast_1d(u)
        d = np.atleast_1d(d)

        # elements already excluded from consideration (e.g. outside an ROI) don't contribute
        # their DQ bits and can't be "the" reason we have no data.
        already_excluded = np.ma.getmaskarray(d)
        rawd = np.ma.getdata(d).astype(np.uint16)

        contributed = np.uint16(np.bitwise_or.reduce(
            np.where(already_excluded, np.uint16(0), rawd), axis=None, initial=np.uint16(0)))

        badmask = already_excluded | ((rawd & BAD) != 0)
        if np.all(badmask):
            # nothing usable was left to aggregate
            return 0.0, 0.0, np.uint16(contributed | NODATA)

        nm = np.ma.masked_array(np.ma.getdata(n), mask=badmask)
        um = np.ma.masked_array(np.ma.getdata(u), mask=badmask)
        dm = np.ma.masked_array(rawd, mask=badmask)

        nr, ur, dqr = func(nm, um, dm)
        return nr, ur, np.uint16(np.uint16(dqr) | contributed)

    if val.tp == Datum.NUMBER:
        ns = val.get(Datum.NUMBER).n
        us = val.get(Datum.NUMBER).u
        dqs = val.get(Datum.NUMBER).dq
        nr, ur, dqr = safe_func(ns, us, dqs)
        return Datum(Datum.NUMBER, Value(nr, ur, dqr), sources=val.sources)
    elif val.isImage():
        img = val.get(Datum.IMG)
        if img is None:
            return None

        # get the subimage (i.e. only the part covered by ROIs if there are any). Bad pixels are
        # deliberately NOT excluded here - safe_func needs to see them to work out which DQ bits
        # were present among the pixels under consideration, before it excludes them itself.
        subimage = img.subimage()
        imgn_masked, imgu_masked, imgd_masked = subimage.masked_all(False)

        if img.channels == 1:
            # mono image
            ns, us, ds = safe_func(imgn_masked, imgu_masked, imgd_masked)
        else:
            # split the image into bands
            ns = imgsplit(imgn_masked)
            us = imgsplit(imgu_masked)
            ds = imgsplit(imgd_masked)
            v = [safe_func(ns[i], us[i], ds[i]) for i in range(0, len(ns))]
            # we now have a list of tuples. We want to get from this:
            # [(n,u,d),(n,u,d),(n,u,d) .. ] to [(n,n,n,n),(u,u,u,u),(d,d,d,d)]
            # so we use zip to transpose the list of tuples
            ns, us, ds = list(zip(*v))
        return Datum(Datum.NUMBER, Value(ns, us, ds), img.sources)
    else:
        # shouldn't happen because we check types
        raise XFormException('DATA', 'stats functions can only take numbers or images')



class Datum(SourcesObtainable):
    """a piece of data sitting in a node's output or on the expression evaluation stack."""
    # the data type
    tp: pcot.datumtypes.Type
    ## @var val
    # the data value
    val: Any
    ## @var sources
    # the source - could be any kind of SourcesObtainable object
    sources: SourcesObtainable

    # register built-in types; extras can be registered with registerType
    types = [
        ANY := pcot.datumtypes.AnyType().setOKForConnectors(),
        IMG := pcot.datumtypes.ImgType().setOKForConnectors(),
        ROI := pcot.datumtypes.RoiType().setOKForConnectors(),
        NUMBER := pcot.datumtypes.NumberType().setOKForConnectors().setOKForParameters(),
        # this special type means the node must have its output/input type specified
        # by the user. They don't appear on the graph until this has happened.
        VARIANT := pcot.datumtypes.VariantType().setOKForConnectors().setOKForParameters(),
        # generic tabular
        TABLE := pcot.datumtypes.TabularDataType().setOKForConnectors(),
        DATA := pcot.datumtypes.GenericDataType().setOKForConnectors(),
        # test results - this is a list of failing tests, or an empty list for all passed.
        TESTRESULT := pcot.datumtypes.TestResultType().setOKForConnectors(),

        # these types are not generally used for connections, but for values on the expression evaluation stack
        IDENT := pcot.datumtypes.IdentType(),
        STRING := pcot.datumtypes.StringType(),
        FUNC := pcot.datumtypes.FuncType(),
        NONE := pcot.datumtypes.NoneType(),  # for neither connections nor the stack - a null value
    ]

    @classmethod
    def registerType(cls, t):
        """Register a custom type, which must be a singleton datum.Type object. You can then use it where you
        would use Datum.IMG, etc. ONLY USE FOR TYPES IN PLUGINS!
        Remember to also register a connector brush with connbrushes.register()."""
        cls.types.append(t)

    null = None  # gets filled in later with a null datum (i.e. type is NONE) that we can use

    def __init__(self, t: pcot.datumtypes.Type, v: Any, sources: Optional[SourcesObtainable] = None):
        """create a datum given the type and value. No type checking is done!
        The source should be a SourcesObtainable object, but can be omitted from images (it will be
        the one stored in the image)."""
        if not isinstance(t, pcot.datumtypes.Type):
            raise BadDatumCtorCallException()

        self.tp = t
        self.val = v

        # type check
        if t.validTypes is not None:
            if not any([isinstance(v, x) for x in t.validTypes]):
                raise InvalidTypeForDatum(f"{str(type(v))} is not a valid type for Datum {t.name}")

        if sources is None:
            if self.isNone():
                sources = nullSource
            elif not self.isImage():
                raise DatumWithNoSourcesException()
            elif self.val is not None:
                if hasattr(self.val, 'sources'):
                    sources = self.val.sources
                else:
                    raise DatumWithNoSourcesException()
            else:
                sources = nullSource
        self.sources = sources

    @classmethod
    def k(cls, n, u=0.0, dq=0):
        """Shortcut method to create a Value object and wrap it in a Datum. Will have null sources, so
        don't use it to create data from observations! That's why it's called "K" for constant."""
        from pcot.value import Value
        if u == 0.0:
            dq |= NOUNCERTAINTY
        return cls(cls.NUMBER, Value(n, u, dq), nullSourceSet)

    def isImage(self):
        """Is this an image of some type?"""
        return self.tp.image

    def isNone(self):
        """is this a null datum? Doesn't matter what the type is."""
        return self.val is None

    def get(self, tp):
        """get data field or None if type doesn't match."""
        if tp == Datum.IMG:
            return self.val if self.isImage() else None
        else:
            return self.val if self.tp == tp else None

    def __str__(self):
        return f"{self.val} ({self.tp})"

    def getSources(self):
        """Get the full source set as an actual single set, unioning all SourceSets within."""
        return self.sources.getSources()

    def serialise(self):
        """Serialise for saving to a file, usually (always?) as the cached value of an input"""
        return self.tp.serialise(self)

    def copy(self):
        """Make a deep copy if the datum is mutable - uses a method in the type to do this"""
        return self.tp.copy(self)

    @classmethod
    def deserialise(cls, data):
        """inverse of serialise for serialised data 'd' - requires document so that sources can be
        reconstructed for images"""

        tp, d = data  # unpack the tuple
        # get the type object
        try:
            t = pcot.datumtypes.typesByName[tp]
        except KeyError:
            raise UnknownDatumTypeException(tp)

        # and run the deserialisation
        return t.deserialise(d)

    def uncertainty(self):
        """Get the uncertainty of the datum as Datum of the same type. For example, an image will return an image of
        uncertainties. A vector will return a scalar."""
        return self.tp.uncertainty(self)

    def getSize(self):
        """Get the size of the datum in bytes. For datum objects with a negligible size, this can be 0."""
        return self.tp.getSize(self)

    def writeBatchOutputFile(self, outputDescription: 'TaggedDict'):
        """Write the datum to an output somehow - delegates to the type object. The input
        is a TaggedDict in the format given by pcot.parameters.runner.OutputDictType"""
        self.tp.writeBatchOutputFile(self, outputDescription)

    #
    # This block of code maps operations on Datum objects to the binary operations registered in the "ops" system
    # by the initOps function (and any other functions that may be run in plugins to register additional types).
    #
    # I'm having to put the ops import inside the methods to avoid a cyclic dependency - basically, Datum really
    # does need to know about ops, and ops really does need to know about Datum.
    #

    def __add__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.ADD, self, other)

    def __sub__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.SUB, self, other)

    def __mul__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.MUL, self, other)

    def __truediv__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.DIV, self, other)

    def __pow__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.POW, self, other)

    def __and__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.AND, self, other)

    def __lt__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.LESSTHAN, self, other)

    def __gt__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.GREATERTHAN, self, other)

    def __or__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.OR, self, other)

    def __neg__(self):
        from pcot.expressions import ops
        return ops.unop(ops.Operator.NEG, self)

    def __invert__(self):
        from pcot.expressions import ops
        return ops.unop(ops.Operator.NOT, self)

    def __rmul__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.MUL, other, self)

    def __radd__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.ADD, other, self)

    def __rsub__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.SUB, other, self)

    def __rtruediv__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.DIV, other, self)

    def __rpow__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.POW, other, self)

    def __rand__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.AND, other, self)

    def __ror__(self, other):
        from pcot.expressions import ops
        return ops.binop(ops.Operator.OR, other, self)

    def __mod__(self, other):
        # we use % instead of $ here.
        from pcot.expressions import ops
        return ops.binop(ops.Operator.DOLLAR, self, other)

    ## wrapped functions! The wrapper will handle turning an ImageCube into Value.

    def sin(self):
        return func_wrapper(lambda x: x.sin(), self)
    def cos(self):
        return func_wrapper(lambda x: x.cos(), self)
    def tan(self):
        return func_wrapper(lambda x: x.tan(), self)
    def sqrt(self):
        return func_wrapper(lambda x: x.sqrt(), self)
    def abs(self):
        # We don't want to inadvertently recurse, so call the builtin
        # abs function.
        return func_wrapper(lambda x: builtins.abs(x), self)

    def mean(self):
        """
        Find the mean±sd of a Datum. This does different things depending on what kind of Datum we are dealing with.
        For a scalar, it just returns the scalar. For a vector, it returns the mean and sd of the vector. For an
        image, it returns a vector of the means and sds of each channel.
        Pixels with "bad" DQ bits will be ignored.
        """
        return stats_wrapper(self, lambda n, u, d: (np.mean(n), pooled_sd(n, u), pcot.dq.NONE))

    def sd(self):
        """
        Find the SD of a Datum. This does different things depending on what kind of Datum we are dealing with.
        For a scalar, it just returns 0. For a vector or single-channel image, it returns a scalar. For an image, it returns a
        vector of the SDs of each channel. Because each individual value in the input set can have its own uncertainty, the
        uncertainty is pooled - the pooled variance is the mean of the variances plus the variance of the means
        (Rudmin, J. W. (2010). Calculating the exact pooled variance. arXiv preprint arXiv:1007.1012). For pooling, we make
        the assumption that the number of items in each input subset (e.g. each pixel) is the same.
        Pixels with "bad" DQ bits will be ignored.
        """
        return stats_wrapper(self, lambda n, u, d: (pooled_sd(n, u), 0, pcot.dq.NOUNCERTAINTY))

    def min(self):
        """
        Find the minimum of a Datum. For a multiband image, returns a vector of the minimum value of each band.
        For a single band image, a scalar, or a vector, returns a scalar.
        Pixels with "bad" DQ bits will be ignored.
        See also the | (OR) operator, which will find the minimum of two values (or images, vectors etc).

        """
        return stats_wrapper(self, lambda n, u, d: minmax(np.argmin, n, u, d))

    def max(self):
        """
        Find the maximum of a Datum. For a multiband image, returns a vector of the maximum of each band.
        For a single band image, a scalar, or a vector, returns a scalar.
        Pixels with "bad" DQ bits will be ignored.
        See also the & (AND) operator, which will find the minimum of two values (or images, vectors etc).

        """
        return stats_wrapper(self, lambda n, u, d: minmax(np.argmax, n, u, d))

    def sum(self):
        """
        Find the sum of a Datum. For a multiband image, returns a vector of the sums of each band.
        For a single band image, a scalar, or a vector, returns a scalar.
        The uncertainty is pooled differently as this is a sum. The variance will be the variance of
        the means plus the sum of the variances (still following
        Rudmin, J. W. (2010). Calculating the exact pooled variance. arXiv preprint arXiv:1007.1012).

        Pixels with "bad" DQ bits will be ignored.
        """
        def sum_of_variances(n, u):
            # we calculate variance of the values in the set
            varianceOfMeans = n.var()
            # we calculate the sum of the variances (not the mean this time!)
            sumOfVariances = np.sum(u ** 2)
            # and return the sum of those two.
            return np.sqrt(varianceOfMeans + sumOfVariances)

        return stats_wrapper(self, lambda n, u, d: (np.sum(n), sum_of_variances(n, u), pcot.dq.NONE))


# a handy null datum object
Datum.null = Datum(Datum.NONE, None)


def deserialise(tp):
    """Given a type name, return the type object; used in deserialising
    macro connectors"""
    try:
        return pcot.datumtypes.typesByName[tp]
    except KeyError:
        raise UnknownDatumTypeException(tp)


def isCompatibleConnection(outtype, intype, inmacro=False):
    """are two connectors compatible?"""
    # this is a weird bug I would really like to catch.
    if intype is None or outtype is None:
        logger.critical("a connectin type is None")
        return False

    # if we're editing a macro, don't flag connections to NONE connectors as being bad - it's
    # likely to be an expr node, which doesn't set its connection type until it runs, and it
    # never will in a macro.
    if inmacro and (intype == Datum.NONE or outtype == Datum.NONE):
        return True

    # variants - used where a node must have a connection type
    # set by the user - cannot connect until they have been so set.
    if intype == Datum.VARIANT or outtype == Datum.VARIANT:
        return False

    # image inputs accept all images
    if intype == Datum.IMG:
        return outtype.image
    elif intype == Datum.ANY:  # accepts anything
        return True
    else:
        # otherwise has to match exactly
        return outtype == intype
