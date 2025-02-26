import pcot.datumtypes
from pcot.cameras.filters import Filter
from pcot.datum import Datum, nullSourceSet
from pcot.datumtypes import Type
from pcot.parameters.taggedaggregates import TaggedDictType, Maybe, TaggedListType

FILTERDICT = TaggedDictType(
    cwl=("Centre wavelength", Maybe(float), None),
    fwhm=("Full-width at half-maximum", Maybe(float), None),
    transmission=("Transmission ratio", float, 1.0),
    position=("Position of filter in camera (e.g. 'L01')", Maybe(str), None),
    name=("Name of filter", Maybe(str), None),
)

FILTERLIST = TaggedListType(FILTERDICT, 0)
CAMDICT = TaggedDictType(
    filters=("List of filters", FILTERLIST),
)


class CameraParams:
    """Holds camera parameters, including filter sets (basically anything that
    isn't large data, like flatfields). It is, as such, only part of the camera data - it's
    created from a datum store and is contained in CameraData"""

    def __init__(self, filters=None):
        """Used when creating an entirely new CameraParams object"""
        self.params = CAMDICT.create()
        if filters:
            self.filters = filters[:] # make a copy
        else:
            self.filters = {}

    @classmethod
    def deserialise(cls, d) -> 'CameraParams':
        self = cls()
        # deserialise the main TaggedDict, and also the TaggedList of filters in their TD form.
        self.params = CAMDICT.deserialise(d)
        # Now convert the TaggedDict filters into a dictionary of Filter objects
        # note that this isn't how filters deserialise themselves (their method is different - legacy)
        self.filters = {f.name: Filter(f.cwl, f.fhwm, f.transmission, f.position, f.name)
                        for f in self.params['filters']}

    def serialise(self):
        # make sure the filters TaggedAggregate is correct by creating it anew from the Filter objects.
        # There is almost certainly a nicer way to do this.
        self.params.filters.clear()
        for k, v in self.filters.items():
            e = self.params.filters.append_default()
            for attr in ('cwl', 'fwhm', 'transmission', 'position', 'name'):
                e[attr] = getattr(v, attr)

        # now we have a fully populated TA and can just serialise everything
        return self.params.serialise()


class CameraParamsType(Type):
    """Holds camera parameters, including filter sets (basically anything that
    isn't large data, like flatfields)"""

    def __init__(self):
        super().__init__('cameradata', valid={CameraParams, type(None)})

    def copy(self, d):
        return d  # this type is immutable

    def serialise(self, d):
        return self.name, d.val.serialise()

    def deserialise(self, d):
        return Datum(self, CameraParams.deserialise(d))

    def getDisplayString(self, d: Datum, box=False):
        return f"Camera data from {d.val.fileName}"


# Create the type singleton and register the type
Datum.registerType(ct := CameraParamsType())
Datum.CAMERAPARAMS = ct


class CameraData:
    """All camera data for a particular camera"""

    def __init__(self, fileName=None):
        """Load the CameraParams object from an archive, and embed it in our new CameraData object. Also store
        the filename of the archive and the archive itself, because we are going to be loading other data (e.g.
        flatfields) when we need them."""
        from pcot.utils.archive import FileArchive
        from pcot.utils.datumstore import DatumStore

        self.fileName = fileName
        self.archive = DatumStore(FileArchive(fileName))

        self.params = self.archive.get("params")
        if self.params is None:
            raise Exception(f"Camera data file {fileName} does not contain camera parameters")
        if self.params.tp != Datum.CAMERAPARAMS:
            raise Exception(f"Camera data file {fileName} contains invalid camera parameters")

    @classmethod
    def write(self, fileName, params: CameraParams):
        """To avoid writing a weird init, we construct a new DatumStore archive here and write a CameraParams
        datum to it. We return the store  so we can write flatfields etc. later. Remember to close the archive!

        The init would be 'weird' because it would have to set up a read/write archive with an LRU cache, and
        that's not a thing that makes a great deal of sense here."""

        from pcot.utils.archive import FileArchive
        from pcot.utils.datumstore import DatumStore

        archive = FileArchive(fileName, "w")
        archive.open()
        da = DatumStore(archive)
        da.writeDatum("params", Datum(Datum.CAMERAPARAMS, params, nullSourceSet))

        return da
