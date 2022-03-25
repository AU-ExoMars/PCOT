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

import pcot.sources
from pcot import rois
from pcot.imagecube import ImageCube
from pcot.sources import SourcesObtainable, nullSource

logger = logging.getLogger(__name__)

## complete list of all types, which also assigns them to values (kind of like an enum)

# lookup by name for serialisation
_typesByName = dict()


class Type:
    """The type of a Datum passed between nodes and inside the expression evaluator.
    Must be a singleton but I'm not going to enforce it."""

    def __init__(self, name, image=False, internal=False):
        self.name = name
        self.image = image  # is the type for an image (i.e. is it a 'subtype' of Type("img")?)
        self.internal = internal  # is it an internal type used in the expression evaluator, not for connectors?
        _typesByName[name] = self  # register by name

    def __str__(self):
        return self.name

    def serialise(self, d):
        raise Exception(f"Datum type {self.name} is not yet serialisable")

    def deserialise(self, d, document) -> 'Datum':
        raise Exception(f"Datum type {self.name} is not yet serialisable")


# Built-in datum types

class AnyType(Type):
    def __init__(self):
        super().__init__('any')


class ImgType(Type):
    def __init__(self):
        super().__init__('img', image=True)

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
        r = rois.deserialise(roidata)
        return Datum(self, r, s)


class NumberType(Type):
    def __init__(self):
        super().__init__('number')

    def serialise(self, d):
        return self.name, (d.val, d.getSources().serialise())

    def deserialise(self, d, document):
        n, s = d
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
            raise XFormException("CODE", "bad call to datum ctor: should be Datum(Type,Value)")

        self.tp = t
        self.val = v

        if sources is None:
            if self.isNone():
                sources = nullSource
            elif not self.isImage():
                raise XFormException("CODE", "Datum objects which are not images must have an explicit source set")
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
            raise Exception(f"{tp} is not a known type")

        # and run the deserialisation
        return t.deserialise(d, document)


# a handy null datum object
Datum.null = Datum(Datum.NONE, None)


def deserialise(n):
    """Given a type name, return the type object; used in deserialising
    macro connectors"""
    if n not in _typesByName:
        raise Exception("cannot find type {} for a connector".format(n))
    return _typesByName[n]


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

