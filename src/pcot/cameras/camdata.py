import pcot.datumtypes
from pcot.datum import Datum
from pcot.datumtypes import Type
from pcot.parameters.taggedaggregates import TaggedDictType, Maybe, TaggedListType

FILTERDICT = TaggedDictType(
    cwl=("Centre wavelength", Maybe(float), None),
    fwhm=("Full-width at half-maximum", Maybe(float), None),
    transmission=("Transmission ratio", float, 1.0),
    position=("Position of filter in camera (e.g. 'L01')", Maybe(str), None),
    name=("Name of filter", Maybe(str), None),
)

CAMDICT = TaggedDictType(
    filters=("List of filters", TaggedListType(FILTERDICT,0))
)


class CameraParams:
    """Holds camera parameters, including filter sets (basically anything that
    isn't large data, like flatfields). It is, as such, only part of the camera data - it's
    created from a datum store and is contained in CameraData"""

    def __init__(self, fileName):
        from pcot.utils.archive import FileArchive
        from pcot.utils.datumstore import DatumStore

        self.fileName = fileName
        self.archive = DatumStore(FileArchive(fileName))

    def serialise(self):
        raise NotImplementedError("CameraParams cannot be serialised")

    @classmethod
    def deserialise(cls, d) -> 'CameraParams':
        raise NotImplementedError("CameraParams cannot be deserialised")


class CameraParamsType(Type):
    """Holds camera parameters, including filter sets (basically anything that
    isn't large data, like flatfields)"""
    def __init__(self):
        super().__init__('cameradata', valid={CameraParams, type(None)})

    def copy(self, d):
        return d    # this type is immutable

    def serialise(self, d):
        return self.name, d.val.serialise()

    def deserialise(self, d):
        return Datum(self, CameraParams.deserialise(d))

    def getDisplayString(self, d: Datum, box=False):
        return f"Camera data from {d.val.fileName}"


# Create the type singleton and register the type
Datum.registerType(ct := CameraParamsType())
Datum.CAMERAPARAMS = ct

