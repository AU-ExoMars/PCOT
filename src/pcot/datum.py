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

from pcot import rois
from pcot.imagecube import ImageCube
from pcot.sources import SourcesObtainable, nullSource, SourceSet

logger = logging.getLogger(__name__)

## complete list of all types, which also assigns them to values (kind of like an enum)

# lookup by name for serialisation
_typesByName = dict()


class DatumException(Exception):
    """Exception class for Datum exceptions. Not (at the moment) a subclass XFormException,
    so gets handled slightly differently when run in a perform()."""
    def __init__(self, message):
        super().__init__(message)


class CannotSerialiseDatumType(DatumException):
    """thrown when we try to serialise/deserialise a datum type which can't be."""
    def __init__(self, typename):
        super().__init__(f"Datum type {typename} is not yet serialisable")


class UnknownDatumTypeException(DatumException):
    """thrown when we try to process an unknown datum type by name."""
    def __init__(self, typename):
        super().__init__(f"Datum type {typename} is unknown")


class BadDatumCtorCallException(DatumException):
    """Thrown when we try to init a datum with the wrong arguments."""
    def __init__(self):
        super().__init__("bad call to datum ctor: should be Datum(Type,Value)")


class DatumWithNoSourcesException(DatumException):
    """Datum constructor should be supplied with explicit source set if not an image or None"""
    def __init__(self):
        super().__init__("Datum objects which are not images must have an explicit source set")


class Type:
    """The type of a Datum passed between nodes and inside the expression evaluator.
    Must be a singleton but I'm not going to enforce it - I did for a while, but it made things
    rather more complicated. Particularly for custom types. Just be careful.
    """

    def __init__(self, name, image=False, internal=False):
        """Parameters:
            name: the name of the type
            image: is the type for an image (i.e. is it a 'subtype' of Type("img")?)
            internal: is it an internal type used in the expression evaluator, not for connectors?
        """
        self.name = name
        self.image = image
        self.internal = internal
        _typesByName[name] = self  # register by name

    def __str__(self):
        return self.name

    def getDisplayString(self, d: 'Datum'):
        """Return the datum as a SHORT string - small enough to fit in a graph box; default
        is just to return the name"""
        return self.name

    def serialise(self, d: 'Datum'):
        raise CannotSerialiseDatumType(self.name)

    def deserialise(self, d, document: 'Document') -> 'Datum':
        raise CannotSerialiseDatumType(self.name)


# Built-in datum types

class AnyType(Type):
    def __init__(self):
        super().__init__('any')

    def getDisplayString(self, d: 'Datum'):
        """Might seem a bit weird, but an unconnected input actually gives "any" as its type."""
        if d.val is None:
            return "none"
        else:
            return "any"


class ImgType(Type):
    def __init__(self):
        super().__init__('img', image=True)

    def getDisplayString(self, d: 'Datum'):
        if d.val is None:
            return "IMG(NONE)"
        else:
            return f"IMG[{d.val.channels}]"

    def serialise(self, d):
        return self.name, d.val.serialise()

    def deserialise(self, d, document):
        img = ImageCube.deserialise(d, document)
        return Datum(self, img)


class ImgRGBType(Type):
    def __init__(self):
        super().__init__('imgrgb', image=True)

    def serialise(self, d):
        return self.name, d.val.serialise()

    def getDisplayString(self, d: 'Datum'):
        if d.val is None:
            return "IMG(NONE)"
        else:
            return "IMG[RGB]"

    def deserialise(self, d, document):
        img = ImageCube.deserialise(d, document)
        return Datum(self, img)


class EllipseType(Type):
    def __init__(self):
        super().__init__('ellipse')


class RoiType(Type):
    def __init__(self):
        super().__init__('roi')

    def serialise(self, d):
        v = d.val
        return self.name, (v.tpname, v.serialise(),
                           v.getSources().serialise())

    def deserialise(self, d, document):
        roitype, roidata, s = d
        s = SourceSet.deserialise(s, document)
        r = rois.deserialise(self.name, roidata)
        return Datum(self, r, s)


class NumberType(Type):
    def __init__(self):
        super().__init__('number')

    def getDisplayString(self, d: 'Datum'):
        return f"{d.val:.5g}"

    def serialise(self, d):
        return self.name, (d.val, d.getSources().serialise())

    def deserialise(self, d, document):
        n, s = d
        s = SourceSet.deserialise(s, document)
        return Datum(self, n, s)


class VariantType(Type):
    def __init__(self):
        super().__init__('variant')


class GenericDataType(Type):
    def __init__(self):
        super().__init__('data')


class IdentType(Type):
    def __init__(self):
        super().__init__('ident', internal=True)


class FuncType(Type):
    def __init__(self):
        super().__init__('func', internal=True)


class NoneType(Type):
    def __init__(self):
        super().__init__('none', internal=True)

    def serialise(self, d):
        return self.name, None

    def deserialise(self, document, d):
        return Datum.null


class Datum(SourcesObtainable):
    """a piece of data sitting in a node's output or on the expression evaluation stack."""
    ## @var tp
    # the data type
    tp: Type
    ## @var val
    # the data value
    val: Any
    ## @var sources
    # the source - could be any kind of SourcesObtainable object
    sources: SourcesObtainable

    # register built-in types; extras can be registered with registerType
    types = [
        ANY := AnyType(),
        # image types, which all contain 'img' in their string (yes, ugly).
        IMG := ImgType(),
        IMGRGB := ImgRGBType(),
        ELLIPSE := EllipseType(),
        ROI := RoiType(),
        NUMBER := NumberType(),
        # this special type means the node must have its output/input type specified
        # by the user. They don't appear on the graph until this has happened.
        VARIANT := VariantType(),
        # generic data
        DATA := GenericDataType(),

        # these types are not generally used for connections, but for values on the expression evaluation stack
        IDENT := IdentType(),
        FUNC := FuncType(),
        NONE := NoneType()  # for neither connections nor the stack - a null value
    ]

    @classmethod
    def registerType(cls, t):
        """Register a custom type, which must be a singleton datum.Type object. You can then use it where you
        would use Datum.IMG, etc.
        Remember to also register a connector brush with connbrushes.register()."""
        cls.types.append(t)

    null = None  # gets filled in later with a null datum (i.e. type is NONE) that we can use

    def __init__(self, t: Type, v: Any, sources: Optional[SourcesObtainable] = None):
        """create a datum given the type and value. No type checking is done!
        The source should be a SourcesObtainable object, but can be omitted from images (it will be
        the one stored in the image)."""
        from pcot.xform import XFormException
        if not isinstance(t, Type):
            raise BadDatumCtorCallException()

        self.tp = t
        self.val = v

        if sources is None:
            if self.isNone():
                sources = nullSource
            elif not self.isImage():
                raise DatumWithNoSourcesException()
            elif self.val is not None:
                sources = self.val.sources
            else:
                sources = nullSource
        self.sources = sources

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
        return "[DATUM-{}, value {}]".format(self.tp, self.val)

    def getSources(self):
        """Get the full source set as an actual single set, unioning all SourceSets within."""
        return self.sources.getSources()

    def serialise(self):
        """Serialise for saving to a file, usually (always?) as the cached value of an input"""
        return self.tp.serialise(self)

    @classmethod
    def deserialise(cls, data, document):
        """inverse of serialise for serialised data 'd' - requires document so that sources can be
        reconstructed for images"""

        tp, d = data  # unpack the tuple
        # get the type object
        try:
            t = _typesByName[tp]
        except KeyError:
            raise UnknownDatumTypeException(tp)

        # and run the deserialisation
        return t.deserialise(d, document)


# a handy null datum object
Datum.null = Datum(Datum.NONE, None)


def deserialise(tp):
    """Given a type name, return the type object; used in deserialising
    macro connectors"""
    try:
        return _typesByName[tp]
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
