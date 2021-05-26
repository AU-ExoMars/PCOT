## @package conntypes
# This deals with the different types of connections between
# xforms. To add a new type, you need to add the type's brush
# (for drawing) to the brushDict here, and you may also need to
# add to isCompatibleConnection if you're doing something odd.
# Note that types which start with "img" are image types, and
# should all be renderable by Canvas.
#
# These types are also used by the expression evaluator.
from typing import Any


# Here is where new connection types are registered and tested
# for compatibility: I'm aware that this should really be model-only,
# but there's UI stuff in here too because (a) I don't want to separate it out and
# (b) there isn't much more to a type than its name.


class Type:
    def __init__(self, name, image=False, internal=False):
        self.name = name
        self.image = image  # is the type for an image (i.e. is it a 'subtype' of Type("img")?)
        self.internal = internal  # is it an internal type used in the expression evaluator, not for connectors?

    def __str__(self):
        return self.name


## complete list of all types
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

# lookup by name for serialisation
typesByName = {t.name: t for t in types}


def deserialise(n):
    if n not in typesByName:
        raise Exception("cannot find type {} for a connector".format(n))
    return typesByName[n]


## are two connectors compatible?
def isCompatibleConnection(outtype, intype):
    # this is a weird bug I would really like to catch.
    if intype is None or outtype is None:
        print("HIGH WEIRDNESS - a connectin type is None")
        return False

    # variants - used where a node must have a connection type
    # set by the user - cannot connect until they have been so set.
    if intype == VARIANT or outtype == VARIANT:
        return False

    # image inputs accept all images
    if intype == IMG:
        return outtype.image
    elif intype == ANY:  # accepts anything
        return True
    else:
        # otherwise has to match exactly
        return outtype == intype


class Datum:
    """a piece of data sitting in a node's output, to be read by its input."""
    ## @var tp
    # the data type
    tp: Type
    ## @var val
    # the data value
    val: Any

    def __init__(self, t: Type, v: Any):
        self.tp = t
        self.val = v

    def isImage(self):
        """Is this an image of some type?"""
        return self.tp.image

    def get(self, tp):
        """get data field or None if type doesn't match."""
        if tp == IMG:
            return self.val if self.isImage() else None
        else:
            return self.val if self.tp == tp else None

    def __str__(self):
        return "[DATUM-{}, value {}]".format(self.tp, self.val)
