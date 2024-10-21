# lookup by name for serialisation
from copy import copy

import numpy as np

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

    instance = None     # the singleton instance of this type

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
        # check the singleton
        if self.__class__.instance is not None:
            raise Exception(f"Type {self.name} is a singleton and already has an instance")
        self.__class__.instance = self
        typesByName[name] = self  # register by name

    def __str__(self):
        return self.name

    def getSize(self, v):
        """Get the size of the value in bytes. This is used to manage the cache in a DatumStore (which is used to
        implement the PARC format).
        By default, items have negligible size. Override this method for types that have a significant size."""
        return 0

    def getDisplayString(self, d: 'Datum', box=False):
        """Return the datum as a fairly brief string - if box is true it must be small enough to fit in a graph box
        or tab title; default is just to return the name"""
        return self.name

    def serialise(self, d: 'Datum'):
        raise pcot.datumexceptions.CannotSerialiseDatumType(self.name)

    def deserialise(self, d, document: 'Document') -> 'Datum':
        raise pcot.datumexceptions.CannotSerialiseDatumType(self.name)

    def copy(self, d):
        """create a copy of the Datum which is an independent piece of data and can be modified independently."""
        raise pcot.datumexceptions.NoDatumCopy(self.name)

    def uncertainty(self, d):
        """Get the uncertainty of the datum as Datum of the same type. For example, an image will return an image of
        uncertainties. A vector will return a scalar."""
        raise pcot.datumexceptions.NoUncertainty(self.name)

    def writeFile(self, d, outputDescription: 'TaggedDict'):
        """Write to a file - this is the default implementation which just writes the
        string representation of the value to a file. The TaggedDict is of OutputDictType, and
        can be found in parameters/runner.py"""
        with open(outputDescription.file, "w") as f:
            f.write(str(d.val))


# Built-in datum types

class AnyType(Type):
    def __init__(self):
        super().__init__('any', valid=None)

    def getDisplayString(self, d: 'Datum', box=False):
        """Might seem a bit weird, but an unconnected input actually gives "any" as its type."""
        if d.val is None:
            return "none"
        else:
            return "any"

    def copy(self, d):
        return d    # this type is immutable


class ImgType(Type):
    def __init__(self):
        # TODO there are reasons why we sometimes might need to create None images. I just can't
        # remember what they are.
        super().__init__('img', image=True, valid={pcot.imagecube.ImageCube, type(None)})

    def getDisplayString(self, d: 'Datum', box=False):
        if d.val is None:
            return "IMG(NONE)"
        else:
            return f"IMG[{d.val.channels}]"

    def serialise(self, d):
        return self.name, d.val.serialise()

    def deserialise(self, d, document):
        img = pcot.imagecube.ImageCube.deserialise(d, document)
        return pcot.datum.Datum(self, img)

    def copy(self, d):
        return pcot.datum.Datum(pcot.datum.Datum.IMG, d.val.copy())

    def uncertainty(self, d):
        return pcot.datum.Datum(pcot.datum.Datum.IMG, d.val.get_uncertainty_image())

    def getSize(self, d):
        v = d.val
        return v.img.nbytes + v.uncertainty.nbytes + v.dq.nbytes

    def writeFile(self, d, fileName):
        v = d.val




class RoiType(Type):
    def __init__(self):
        from pcot.rois import ROI
        super().__init__('roi', valid={ROI, type(None)})

    def serialise(self, d):
        v = d.val
        return self.name, (v.tpname, v.serialise(),
                           v.getSources().serialise())

    def deserialise(self, d, document):
        roitype, roidata, s = d
        s = pcot.sources.SourceSet.deserialise(s, document)
        r = pcot.rois.deserialise(self.name, roidata)
        return pcot.datum.Datum(self, r, s)

    def copy(self, d):
        r = copy(d.val)  # deep copy with __copy__
        return pcot.datum.Datum(pcot.datum.Datum.ROI, r)

    def getSize(self, v):
        return v.getSize()


class NumberType(Type):
    """Number datums contain a Value object (scalar or vector, currently)."""
    def __init__(self):
        super().__init__('number', valid=[pcot.value.Value])

    def getDisplayString(self, d: 'Datum', box=False):
        """in the graph box, a vec is just displayed as VEC[n] where n is the number of elements"""
        if box and not np.isscalar(d.val.n):
            return f"VEC[{d.val.n.shape[0]}]"
        return str(d.val)

    def serialise(self, d):
        return self.name, (d.val.serialise(),
                           d.getSources().serialise())

    def deserialise(self, d, document):
        n, s = d
        n = pcot.value.Value.deserialise(n)
        s = pcot.sources.SourceSet.deserialise(s, document)
        return pcot.datum.Datum(self, n, s)

    def copy(self, d):
        return d    # this type is immutable

    def uncertainty(self, d):
        return pcot.datum.Datum(pcot.datum.Datum.NUMBER, pcot.value.Value(d.val.uncertainty()), d.getSources())

    def getSize(self, d):
        if np.isscalar(d.val.n):
            return 0
        else:
            return d.val.n.nbytes + d.val.u.nbytes + d.val.dq.nbytes


class VariantType(Type):
    def __init__(self):
        super().__init__('variant', valid=None)

    def copy(self, d):
        return d    # this type is immutable


class GenericDataType(Type):
    def __init__(self):
        super().__init__('data', valid=None)

    def copy(self, d):
        return d    # this type is immutable


class TestResultType(Type):
    def __init__(self):
        super().__init__('testresult', valid=[list])

    def getDisplayString(self, d: 'Datum', box=False):
        failed = len(d.val)
        if failed > 0:
            return f"FAILED {failed}"
        else:
            return "TESTS OK"

    def copy(self, d):
        return d    # this type is immutable


class IdentType(Type):
    def __init__(self):
        super().__init__('ident', internal=True, valid=[str])

    def copy(self, d):
        return d    # this type is immutable


class StringType(Type):
    def __init__(self):
        super().__init__('string', internal=True, valid=[str])

    def copy(self, d):
        return d    # this type is immutable


class FuncType(Type):
    def __init__(self):
        super().__init__('func', internal=True, valid=None)

    def copy(self, d):
        return d    # this type is immutable


class NoneType(Type):
    def __init__(self):
        super().__init__('none', internal=True)

    def serialise(self, d):
        return self.name, None

    def deserialise(self, document, d):
        from pcot.datum import Datum
        return Datum.null

    def copy(self, d):
        return d    # this type is immutable

