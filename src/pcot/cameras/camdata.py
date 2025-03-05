from pcot.cameras.filters import DUMMY_FILTER
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
    name=("Name of camera", Maybe(str), None),
    date=("Date of camera data", Maybe(str), None),
    author=("Author of camera data", Maybe(str), None),
    description=("Description of camera data", Maybe(str), None),
    short=("Short description of camera data", Maybe(str), None),
    filters=("List of filters", FILTERLIST),
)


class CameraParams:
    """Holds camera parameters, including filter sets (basically anything that
    isn't large data, like flatfields). It is, as such, only part of the camera data - it's
    created from a datum store and is contained in CameraData"

    This object has a "params" field, which is a TaggedDict and stores basic stuff (name, description etc).
    It also itself forms the "params" field of a CameraData object, so we get "amusing" little chains like
    camera.params.params.name. Sorry.

    """

    def __init__(self, filters=None):
        """Used when creating an entirely new CameraParams object. The input is:

        * filters: a dict of filter objects {name:data}
        """
        self.params = CAMDICT.create()
        if filters:
            self.filters = filters.copy()
        else:
            self.filters = {}

        # backpointer to the CameraData object so we can get the archive; will be set by CameraData
        self.camera_data = None

    @classmethod
    def deserialise(cls, d) -> 'CameraParams':
        from pcot.cameras.filters import Filter
        p = cls()
        # deserialise the main TaggedDict, and also the TaggedList of filters in their TD form.
        p.params = CAMDICT.deserialise(d)
        # make sure the mandatory fields are there
        for k in ('name', 'date', 'author', 'description'):
            if p.params[k] is None:
                raise ValueError(f"Camera data missing mandatory field '{k}'")

        # Now convert the TaggedDict filters into a dictionary of Filter objects
        # note that this isn't how filters deserialise themselves (their method is different - legacy)
        p.filters = {f.name: Filter(f.cwl, f.fwhm, f.transmission, f.position, f.name, params=p)
                     for f in p.params['filters']}
        return p

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
        # We assume that there is no useful source data we can add. This may change.
        return Datum(self, CameraParams.deserialise(d), nullSourceSet)

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

        try:
            self.fileName = fileName
            self.archive = DatumStore(FileArchive(fileName))
            self.params = self.archive.get("params")
            if self.params is None:
                raise Exception(f"Camera data file {fileName} does not contain camera parameters")
            if self.params.tp != Datum.CAMERAPARAMS:
                raise Exception(f"Camera data file {fileName} contains invalid camera parameters")
        except Exception as e:
            raise Exception(f"Error opening camera data file {fileName}: {str(e)}")

        # resolve the Datum object
        self.params = self.params.val

        # set up the backpointer so CameraParams and Filter can get the archive if we need to load
        # more data
        self.params.camera_data = self


    @classmethod
    def openStoreAndWrite(self, fileName, params: CameraParams):
        """To avoid writing a weird init, we construct a new DatumStore archive here and write a CameraParams
        datum to it. We return the store  so we can write flatfields etc. later. Remember to close the archive!

        The init would be 'weird' because it would have to set up a read/write archive with an LRU cache, and
        that's not a thing that makes a great deal of sense here."""

        from pcot.utils.archive import FileArchive
        from pcot.utils.datumstore import DatumStore

        archive = FileArchive(fileName, "w")
        archive.open()
        ds = DatumStore(archive)
        ds.writeDatum("params", Datum(Datum.CAMERAPARAMS, params, nullSourceSet))
        return ds

    def getFilter(self, target, search):
        """Get the filter from the camera data. The search parameter is one of 'name', 'pos' or 'cwl'."""

        def get_match(params, key, value):
            matches = []
            for x in params.filters.values():
                if getattr(x, key) == value:
                    matches.append(x)
            if len(matches) > 1:
                raise ValueError(f"Multiple matches for {key}={value}")
            elif len(matches) == 0:
                return DUMMY_FILTER
            else:
                return matches[0]

        if search == 'name':
            # this one is easy, it's the key of the filter dict.
            return self.params.filters.get(target, DUMMY_FILTER)
        elif search == 'pos':
            # for the others we need to do a search, and throw an error if there are multiple matches
            return get_match(self.params, 'position', target)
        elif search == 'cwl':
            return get_match(self.params, 'cwl', target)
        else:
            return DUMMY_FILTER
