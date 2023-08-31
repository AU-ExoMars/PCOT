

# lookup by name for serialisation
import pcot.rois
import pcot.datumexceptions
import pcot.imagecube
import pcot.sources
import pcot.value
import pcot.datum
import pcot.sources

typesByName = dict()


class Type:
    """The type of a Datum passed between nodes and inside the expression evaluator.
    Must be a singleton but I'm not going to enforce it - I did for a while, but it made things
    rather more complicated. Particularly for custom types. Just be careful.
    """

    def __init__(self, name, image=False, internal=False, valid=None):
        """Parameters:
            name: the name of the type
            image: is the type for an image (i.e. is it a 'subtype' of Type("img")?)
            internal: is it an internal type used in the expression evaluator, not for connectors?
            valid: set of valid types of which the Datum's value must be an instance, or None for anything
        """
        self.name = name
        self.image = image
        self.internal = internal
        self.validTypes = valid
        typesByName[name] = self  # register by name

    def __str__(self):
        return self.name

    def getDisplayString(self, d: 'Datum'):
        """Return the datum as a SHORT string - small enough to fit in a graph box; default
        is just to return the name"""
        return self.name

    def serialise(self, d: 'Datum'):
        raise pcot.datumexceptions.CannotSerialiseDatumType(self.name)

    def deserialise(self, d, document: 'Document') -> 'Datum':
        raise pcot.datumexceptions.CannotSerialiseDatumType(self.name)


# Built-in datum types

class AnyType(Type):
    def __init__(self):
        super().__init__('any', valid=None)

    def getDisplayString(self, d: 'Datum'):
        """Might seem a bit weird, but an unconnected input actually gives "any" as its type."""
        if d.val is None:
            return "none"
        else:
            return "any"


class ImgType(Type):
    def __init__(self):
        # TODO there are reasons why we sometimes might need to create None images. I just can't
        # remember what they are.
        super().__init__('img', image=True, valid={pcot.imagecube.ImageCube, type(None)})

    def getDisplayString(self, d: 'Datum'):
        if d.val is None:
            return "IMG(NONE)"
        else:
            return f"IMG[{d.val.channels}]"

    def serialise(self, d):
        return self.name, d.val.serialise()

    def deserialise(self, d, document):
        img = pcot.imagecube.ImageCube.deserialise(d, document)
        return pcot.datum.Datum(self, img)


class RoiType(Type):
    def __init__(self):
        from pcot.rois import ROI
        super().__init__('roi', valid={ROI})

    def serialise(self, d):
        v = d.val
        return self.name, (v.tpname, v.serialise(),
                           v.getSources().serialise())

    def deserialise(self, d, document):
        roitype, roidata, s = d
        s = pcot.sources.SourceSet.deserialise(s, document)
        r = pcot.rois.deserialise(self.name, roidata)
        return pcot.datum.Datum(self, r, s)


class NumberType(Type):
    """Number datums contain a scalar OpData object."""
    def __init__(self):
        super().__init__('number', valid=[pcot.value.Value])

    def getDisplayString(self, d: 'Datum'):
        return f"{d.val.n:.5g}±{d.val.u:.5g}"

    def serialise(self, d):
        return self.name, (d.val.serialise(),
                           d.getSources().serialise())

    def deserialise(self, d, document):
        n, s = d
        n = pcot.value.Value.deserialise(n)
        s = pcot.sources.SourceSet.deserialise(s, document)
        return pcot.datum.Datum(self, n, s)


class VariantType(Type):
    def __init__(self):
        super().__init__('variant', valid=None)


class GenericDataType(Type):
    def __init__(self):
        super().__init__('data', valid=None)


class TestResultType(Type):
    def __init__(self):
        super().__init__('testresult', valid=[list])

    def getDisplayString(self, d: 'Datum'):
        failed = len(d.val)
        if failed > 0:
            return f"FAILED {failed}"
        else:
            return "TESTS OK"


class IdentType(Type):
    def __init__(self):
        super().__init__('ident', internal=True, valid=[str])


class FuncType(Type):
    def __init__(self):
        super().__init__('func', internal=True, valid=None)


class NoneType(Type):
    def __init__(self):
        super().__init__('none', internal=True)

    def serialise(self, d):
        return self.name, None

    def deserialise(self, document, d):
        from pcot.datum import Datum
        return Datum.null


