"""This deals with the different types of connections between xforms.
To add a new type, you need to add the type's brush
(for drawing) to the brushDict here, and you may also need to
add to isCompatibleConnection if you're doing something odd.
Note that types which start with "img" are image types, and
should all be renderable by Canvas.
These types are also used by the expression evaluator.
"""
import logging
from typing import Any, Optional

from pcot.dq import NOUNCERTAINTY
from pcot.rois import ROI
from pcot.sources import SourcesObtainable, nullSource, nullSourceSet
import pcot.datumtypes

from pcot.datumexceptions import *

logger = logging.getLogger(__name__)


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
        ANY := pcot.datumtypes.AnyType(),
        IMG := pcot.datumtypes.ImgType(),
        ROI := pcot.datumtypes.RoiType(),
        NUMBER := pcot.datumtypes.NumberType(),
        # this special type means the node must have its output/input type specified
        # by the user. They don't appear on the graph until this has happened.
        VARIANT := pcot.datumtypes.VariantType(),
        # generic data
        DATA := pcot.datumtypes.GenericDataType(),
        # test results - this is a list of failing tests, or an empty list for all passed.
        TESTRESULT := pcot.datumtypes.TestResultType(),

        # these types are not generally used for connections, but for values on the expression evaluation stack
        IDENT := pcot.datumtypes.IdentType(),
        STRING := pcot.datumtypes.StringType(),
        FUNC := pcot.datumtypes.FuncType(),
        NONE := pcot.datumtypes.NoneType()  # for neither connections nor the stack - a null value
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
        return "<DATUM-{}, value {}>".format(self.tp, self.val)

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


# a handy null datum object
Datum.null = Datum(Datum.NONE, None)


def deserialise(tp):
    """Given a type name, return the type object; used in deserialising
    macro connectors"""
    try:
        return pcot.datumtypes.typesByName[tp]
    except KeyError:
        raise UnknownDatumTypeException(tp)


def isCompatibleConnection(outtype, intype):
    """are two connectors compatible?"""
    # this is a weird bug I would really like to catch.
    if intype is None or outtype is None:
        logger.critical("a connectin type is None")
        return False

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
