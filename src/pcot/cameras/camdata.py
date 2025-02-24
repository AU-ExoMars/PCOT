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


class CameraData:
    def __init__(self, fileName):
        """The camera data object is created from a datum archive"""
        from pcot.utils.archive import FileArchive
        from pcot.utils.datumstore import DatumStore

        self.fileName = fileName
        self.archive = DatumStore(FileArchive(fileName))

        # we want to deserialise a Datum from that archive's data.