"""This deals with the different types of connections between xforms.
To add a new type, you need to add the type's brush
(for drawing) to the brushDict here, and you may also need to
add to isCompatibleConnection if you're doing something odd.
Note that types which start with "img" are image types, and
should all be renderable by Canvas.
These types are also used by the expression evaluator.
"""

from typing import Any, Optional

from pcot.sources import SourcesObtainable


class Type:
    """The type of a Datum passed between nodes and inside the expression evaluator."""
    def __init__(self, name, image=False, internal=False):
        self.name = name
        self.image = image  # is the type for an image (i.e. is it a 'subtype' of Type("img")?)
        self.internal = internal  # is it an internal type used in the expression evaluator, not for connectors?

    def __str__(self):
        return self.name


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

    types = [
        ANY := Type("any"),
        # image types, which all contain 'img' in their string (yes, ugly).
        IMG := Type("img", image=True),
        IMGRGB := Type("imgrgb", image=True),
        ELLIPSE := Type("ellipse"),
        ROI := Type("roi"),
        NUMBER := Type("number"),
        # this special type means the node must have its output/input type specified
        # by the user. They don't appear on the graph until this has happened.
        VARIANT := Type("variant"),
        # generic data
        DATA := Type("data"),

        # these types are not generally used for connections, but for values on the expression evaluation stack
        IDENT := Type("ident", internal=True),
        FUNC := Type("func", internal=True)
    ]

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
            if not self.isImage():
                raise XFormException("CODE", "Datum objects which are not images must have an explicit source set")
            else:
                sources = self.val.sources
        self.sources = sources

    def isImage(self):
        """Is this an image of some type?"""
        return self.tp.image

    def get(self, tp):
        """get data field or None if type doesn't match."""
        if tp == Datum.IMG:
            return self.val if self.isImage() else None
        else:
            return self.val if self.tp == tp else None

    def __str__(self):
        return "[DATUM-{}, value {}]".format(self.tp, self.val)

    def getSources(self):
        return self.sources.getSources()


## complete list of all types, which also assigns them to values (kind of like an enum)

# lookup by name for serialisation
_typesByName = {t.name: t for t in Datum.types}


def deserialise(n):
    """Given a type name, return the type object"""
    if n not in _typesByName:
        raise Exception("cannot find type {} for a connector".format(n))
    return _typesByName[n]


def isCompatibleConnection(outtype, intype):
    """are two connectors compatible?"""
    # this is a weird bug I would really like to catch.
    if intype is None or outtype is None:
        print("HIGH WEIRDNESS - a connectin type is None")
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
