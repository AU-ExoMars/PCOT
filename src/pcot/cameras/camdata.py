import logging
import re

from pcot.cameras.filters import DUMMY_FILTER
from pcot.cameras.filtresponse import FilterResponse
from pcot.datum import Datum, nullSourceSet
from pcot.datumtypes import Type
from pcot.parameters.taggedaggregates import TaggedDictType, Maybe, TaggedListType

logger = logging.getLogger(__name__)

FILTERDICT = TaggedDictType(
    cwl=("Centre wavelength", Maybe(float), None),
    fwhm=("Full-width at half-maximum", Maybe(float), None),
    transmission=("Transmission ratio", float, 1.0),
    position=("Position of filter in camera (e.g. 'L01')", Maybe(str), None),
    name=("Name of filter", Maybe(str), None),
    response=("Filter response data", Maybe(dict), None),   # the dict is a serialised FilterResponse object
    order=("Super-Gaussian order used only when simulating the response (1 = standard Gaussian)", float, 1.0),
)

FILTERLIST = TaggedListType(FILTERDICT, 0)
CAMDICT = TaggedDictType(
    name=("Name of camera", Maybe(str), None),
    date=("Date of camera data", Maybe(str), None),
    compilation_time=("Date and time of camera data compilation", Maybe(str), None),
    author=("Author of camera data", Maybe(str), None),
    description=("Description of camera data", Maybe(str), None),
    short=("Short description of camera data", Maybe(str), None),
    source_filename=("Name of YAML file from which data was generated", Maybe(str), None),
    has_flats=("Does this camera have flatfields?", bool, False),       # for information only, not used in the code
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

        * filters: a dict of Filter objects {name:data}
        """
        self.params = CAMDICT.create()
        if filters:
            self.filters = filters.copy()
        else:
            self.filters = {}

    @classmethod
    def deserialise(cls, d) -> 'CameraParams':
        # this deserialisation is only done as part of the CameraParams load from the camera
        # data archive.
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
        # UGLY - we have to patch the camera name into the filters "upstairs" in CameraData, because
        # we can't get it here.
        def deser_response(d):
            return None if d is None else FilterResponse.deserialise(d)

        p.filters = {f.name: Filter(f.cwl, f.fwhm, f.transmission, f.position, f.name,
                                    None, response=deser_response(f.response), order=f.order)
                     for f in p.params['filters']}

        for f in p.filters.values():
            if isinstance(f, Filter) and f.response is not None:
                if f.response.clipped_to:
                    logger.warning(f"Camera data response for {f.name} is over {f.response.clipped_to}% and has been clipped")
        return p

    def serialise(self):
        # make sure the filters TaggedAggregate is correct by creating it anew from the Filter objects.
        # There is almost certainly a nicer way to do this.
        self.params.filters.clear()
        for k, v in self.filters.items():
            e = self.params.filters.append_default()
            for attr in ('cwl', 'fwhm', 'transmission', 'position', 'name', 'order'):
                e[attr] = getattr(v, attr)
            # save a serialised version of the filter response - this include nparrays, but that
            # is still serialisable if we're saving to a FileArchive.
            e['response'] = None if v.response is None or v.response.is_simulated else v.response.serialise()

        # now we have a fully populated TA and can just serialise everything
        d = self.params.serialise()
        return d


class CameraParamsType(Type):
    """To make life easier for serialisation, this is a DatumType. Holds camera parameters, including filter sets
    (basically anything that isn't large data, like flatfields or filter profiles). The larger items are stored
    in the CameraData object, which contains this one."""

    def __init__(self):
        super().__init__('cameradata', valid={CameraParams, type(None)},internal=True)

    def copy(self, d):
        return d  # this type is immutable

    def serialise(self, d):
        return self.name, d.val.serialise()

    def deserialise(self, d):
        # We assume that there is no useful source data we can add. This may change.
        return Datum(self, CameraParams.deserialise(d), nullSourceSet)

    def getDisplayString(self, d: Datum, box=False):
        return f"Camera data from {d.val.fileName}"
        
    def view(self, d):
        import json
        return json.dumps(d.val.serialise(),indent=2)
        

# Create the type singleton and register the type
Datum.registerType(ct := CameraParamsType())
Datum.CAMERAPARAMS = ct


class CameraData:
    """All camera data for a particular camera"""

    def __init__(self, fileName=None):
        """Load the CameraParams object from an archive, and embed it in our new CameraData object. Also store
        the filename of the archive and the archive itself, because we are going to be loading other data (e.g.
        flatfields) when we need them."""
        from pcot.utils.archive import FileArchive, ArchiveType
        from pcot.utils.datumstore import DatumStore

        try:
            self.fileName = fileName
            self.archive = DatumStore(FileArchive(fileName))
            if self.archive.archive.metadata.type != ArchiveType.CAMERADATA:
                logger.warning(f"{fileName} is not a camera archive (type={self.archive.archive.metadata.type}) - is it legacy? Will try to load anyway.")
            self.params = self.archive.get("params")
            if self.params is None:
                raise Exception(f"Camera data file {fileName} does not contain camera parameters")
            if self.params.tp != Datum.CAMERAPARAMS:
                raise Exception(f"Camera data file {fileName} contains invalid camera parameters")
        except Exception as e:
            raise Exception(f"Error opening camera data file {fileName}: {str(e)}")

        # resolve the Datum object
        self.params = self.params.val
        # now we need to patch the filters so they have the camera name
        for x in self.params.filters.values():
            x.camera_name = self.params.params.name

    @classmethod
    def openStoreAndWrite(self, fileName, params: CameraParams):
        """To avoid writing a weird init, we construct a new DatumStore archive here and write a CameraParams
        datum to it. We return the store  so we can write flatfields etc. later. Remember to close the archive!
        This is called from the gencam command.

        The init would be 'weird' because it would have to set up a read/write archive with an LRU cache, and
        that's not a thing that makes a great deal of sense here."""

        from pcot.utils.archive import FileArchive,ArchiveType,Metadata
        from pcot.utils.datumstore import DatumStore

        # get extra metadata that's in the dict; there's some kinda duplication here because the author and
        # date stored in the metadata will be automatically generated from the system and won't be the values
        # stored in the YAML file. I think that might be a good idea - the metadata on the archive is about
        # the file, but the metadata in the data itself is about that data.
        meta = Metadata(type=ArchiveType.CAMERADATA,
                                description=params.params.description,
                                name=params.params.name,
                                short=params.params.short)
        archive = FileArchive(fileName, "w", metadata=meta)
        archive.open()
        ds = DatumStore(archive)
        ds.writeDatum("params", Datum(Datum.CAMERAPARAMS, params, nullSourceSet))
        return ds

    def getFilter(self, target, search='name'):
        """Get the filter from the camera data. The search parameter is one of 'name', 'pos' or 'cwl'. On failure,
        returns a dummy filter with a zero cwl."""

        def get_match(params, key, value):
            matches = []
            target_is_numeric = False
            if key == 'position':
                # position matches are numeric IF the target we are looking for is a valid integer
                # Otherwise they are string matches. This makes sure that "2" = "02" but that "L03" also
                # works as a target
                try:
                    value = int(value)
                    target_is_numeric = True
                except ValueError:
                    pass

            for x in params.filters.values():
                v_in_filter = getattr(x, key)
                # position matches are numeric!
                if key == 'position' and target_is_numeric:
                    try:
                        v_in_filter = float(v_in_filter)
                    except ValueError:
                        v_in_filter = -100  # make sure it won't match if it's not a float
                if v_in_filter == value:
                    matches.append(x)
                else:
                    # if both the filter pos in the camera (e.g.L01) and the name from the file (e.g.L1) consist of
                    # "<string><digits>" then allow a match if the strings are the same and the int represented by
                    # the digits is the same.
                    matches_in_value = re.match(r"^([a-zA-Z]+)([0-9]+)$", str(value))
                    matches_in_filter = re.match(r"^([a-zA-Z]+)([0-9]+)$", str(v_in_filter))
                    if matches_in_filter and matches_in_value:
                        if matches_in_value.group(1) == matches_in_filter.group(1) and \
                                int(matches_in_value.group(2)) == int(matches_in_filter.group(2)):
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

    def getFlat(self, filtname) -> Datum:
        """Get the flatfield for the given filter and position."""
        return self.archive.get(f"flat_{filtname}")
