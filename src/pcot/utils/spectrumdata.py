"""
The serialisable spectrum classes: SpectrumValue, Spectrum and SpectrumSet (which is what a spectra Datum carries).
These hold no references to images or ROIs, so spectra can come from anywhere - extracted from an
ImageCube (see spectrum.py) or loaded from a point spectrometer.
This is kept separate from the extraction code in spectrum.py, which depends on the xform machinery,
so that datumtypes can import it without a circular import.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple, List, Iterator, Any

from pcot import config
from pcot.cameras.filters import Filter
from pcot.config import ConfigSectionHandler
from pcot.parameters.taggedaggregates import TaggedDict, TaggedDictType
from pcot.sources import SourceSet, SourcesObtainable
from pcot.utils.table import printable, Table
from pcot.utils.tabular_provider import TabularProvider, TabularIterator, naturalSortKey
from pcot.value import Value


class SpectrumValue:
    """A single value in a spectrum and the number of pixels from which it was obtained.
    It can return JSON-serialisable data and be deserialised from such data.

    TODO: the pixel count is used to calculate standard errors (sd/sqrt(pixels)), so a spectrum
    from a point spectrometer (e.g. Enfys) will need to decide what to put here."""
    v: Value
    pixels: int  # the number of pixels from which the value was obtained

    def __init__(self, v: Value, pixels: int):
        self.v = v
        # and this is why this isn't a dataclass. What gets passed in is typically
        # an int32, which isn't JSON-serialisable.
        self.pixels = int(pixels)

    def as_tuple(self):
        return self.v, self.pixels

    def serialise(self):
        return [self.v.serialise(), self.pixels]

    @staticmethod
    def deserialise(d):
        serv, serp = d
        return SpectrumValue(Value.deserialise(serv), serp)


class Spectrum:
    """A single spectrum: a value for each of a set of filters, and an optional colour to plot it in
    (taken from the ROI for spectra extracted from images). Only filters which have a value are present."""

    # the spectrum as a dictionary of filter:value (typically reflectance)
    values: Dict[Filter, SpectrumValue]
    # colour to plot this spectrum in, or None to let the plot choose
    colour: Optional[Tuple[float, float, float]]
    # each wavelength's filter - if two filters share a wavelength, only one will be here
    filters_by_wavelength: Dict[float, Filter]

    def __init__(self, values: Dict[Filter, SpectrumValue], colour: Optional[Tuple[float, float, float]] = None):
        self.values = values
        # colours from ROIs may be numpy floats, which aren't JSON-serialisable
        self.colour = tuple(float(c) for c in colour) if colour is not None else None
        self.filters_by_wavelength = {f.cwl: f for f in values}

    def get(self, cwlOrName) -> Optional[SpectrumValue]:
        """get the value and pixel count for a particular channel wavelength or filter name"""
        for f, v in self.values.items():
            if f.cwl == cwlOrName or f.name == cwlOrName:
                return v
        return None

    def valueAtWavelength(self, w: float) -> Optional[SpectrumValue]:
        """get the value for the filter at a wavelength, or None if there isn't one"""
        f = self.filters_by_wavelength.get(w)
        return self.values[f] if f is not None else None

    def filters(self) -> List[Filter]:
        """the filters which have values, sorted by wavelength"""
        return sorted(self.values.keys(), key=lambda f: f.cwl)

    def hasDuplicateWavelengths(self) -> bool:
        """true if two filters share a wavelength, which can't be shown in tables"""
        return len(self.filters_by_wavelength) != len(self.values)

    def __repr__(self):
        return "Spectrum: " + "; ".join([f"{f}:{v}" for f, v in self.values.items()])


class SpectrumSet(SourcesObtainable):
    """A set of named spectra - this is what a spectra Datum carries. The names are typically ROI names
    (or "image:ROI" names if the same ROI name appears in more than one image). It can be used
    as a read-only dict of name to Spectrum.

    It can be serialised, including the full data for each filter (each distinct filter is only stored once).
    The sources are not serialised, because they are held in the containing Datum.

    To create one from images and their ROIs, use SpectrumSet.fromImages().
    """

    spectra: Dict[str, Spectrum]
    sources: SourceSet

    def __init__(self, spectra: Dict[str, Spectrum], sources: Optional[SourceSet] = None):
        self.spectra = spectra
        self.sources = sources if sources is not None else SourceSet()

    @staticmethod
    def fromImages(images, ignorePixSD=False) -> SpectrumSet:
        """Create a set of spectra from a dictionary of ImageCube objects and the ROIs they contain;
        see spectraFromImages() in pcot.utils.spectrum."""
        # imported here because spectrum.py depends on the xform machinery
        from pcot.utils.spectrum import spectraFromImages
        return spectraFromImages(images, ignorePixSD=ignorePixSD)

    @staticmethod
    def merge(parts: Dict[str, SpectrumSet], base: Optional[SpectrumSet] = None) -> SpectrumSet:
        """Merge several spectrum sets into one, combining their sources. The base set's names are kept
        as they are. A name in one of the parts which is also in the base or in another part is prefixed
        with the part's key and a colon (e.g. "in5:1"); if that still clashes, it's an error."""
        spectra = dict(base.spectra) if base is not None else {}
        sources = [base.sources] if base is not None else []

        # count how many times each name appears across the base and the parts
        counts = {}
        for ss in ([base] if base is not None else []) + list(parts.values()):
            for name in ss.spectra:
                counts[name] = counts.get(name, 0) + 1

        for partname, ss in parts.items():
            for name, spectrum in ss.spectra.items():
                newname = f"{partname}:{name}" if counts[name] > 1 else name
                if newname in spectra:
                    raise ValueError(f"spectrum name {newname} appears more than once")
                spectra[newname] = spectrum
            sources.append(ss.sources)

        return SpectrumSet(spectra, SourceSet(sources))

    # read-only dict access

    def __getitem__(self, name) -> Spectrum:
        return self.spectra[name]

    def __contains__(self, name):
        return name in self.spectra

    def __iter__(self):
        return iter(self.spectra)

    def __len__(self):
        return len(self.spectra)

    def keys(self):
        return self.spectra.keys()

    def items(self):
        return self.spectra.items()

    def values(self):
        return self.spectra.values()

    def getSources(self) -> SourceSet:
        """return a set of all the sources in the spectra"""
        return self.sources

    def serialise(self):
        # each distinct filter is stored once, and referred to by index
        filters = []
        filterIndices: Dict[Filter, int] = {}
        spectra = {}
        for name, spectrum in self.spectra.items():
            values = []
            for f, v in spectrum.values.items():
                if f not in filterIndices:
                    filterIndices[f] = len(filters)
                    filters.append(f)
                values.append([filterIndices[f], v.serialise()])
            spectra[name] = {
                "colour": list(spectrum.colour) if spectrum.colour is not None else None,
                "values": values,
            }
        return {
            "filters": [f.serialise() for f in filters],
            "spectra": spectra,
        }

    @staticmethod
    def deserialise(data) -> SpectrumSet:
        """Deserialise; the sources are not part of the serialised data and must be set separately."""
        filters = [Filter.deserialise(f) for f in data["filters"]]
        spectra = {}
        for name, d in data["spectra"].items():
            values = {filters[idx]: SpectrumValue.deserialise(v) for idx, v in d["values"]}
            spectra[name] = Spectrum(values, d["colour"])
        return SpectrumSet(spectra)

    def table(self) -> Table:
        """Return a Table representation (as used in older versions of PCOT)"""
        provider = self.tabularProvider()
        table = Table()
        for row in provider:
            table.newRow(row["name"])
            for k in provider.getHeaders():
                table.add(k, row[k])
        return table

    #
    # Indexing from expressions, e.g. a[0,440] or a[0,m440,s440]
    #

    def getByIndices(self, args, sources):
        """Given a list of Datum index objects, return a Datum for the value they indicate. The first index
        is the spectrum name (an integer like 0 is looked up as the name "0"). Then either:
            - a wavelength number, giving the spectrum's Value at that wavelength (with uncertainty and DQ)
            - a column name as in the tabular output (m440, s440 or p440 for mean, SD and pixel count),
              optionally followed by a second column name which gives the uncertainty. This is how
              spectra were indexed when they were output as tables.
        Unknown spectra, columns and wavelengths are errors."""
        from pcot.datum import Datum

        if len(args) < 2:
            raise ValueError("spectra need a name and a wavelength or column, e.g. a[0,440] or a[0,m440,s440]")
        if len(args) > 3:
            raise ValueError("too many indices for spectra")

        # first, find the spectrum
        d = args[0]
        if d.tp == Datum.NUMBER:
            if not d.val.isscalar():
                raise ValueError("cannot use a vector as an index")
            if d.val.n != int(d.val.n):
                raise ValueError(f"spectrum name {d.val.n} is not a whole number")
            name = str(int(d.val.n))
        elif d.tp == Datum.IDENT or d.tp == Datum.STRING:
            name = d.val
        else:
            raise ValueError(f"cannot use a {d.tp.name} as a spectrum name")
        if name not in self.spectra:
            raise KeyError(f"no spectrum called {name}")
        spectrum = self.spectra[name]

        def valueAtWavelength(w) -> SpectrumValue:
            v = spectrum.valueAtWavelength(w)
            if v is None:
                raise ValueError(f"spectrum {name} has no value at wavelength {w:g}")
            return v

        def column(d):
            """find the SpectrumValue and the part of it (m, s or p) named by a column index"""
            if d.tp != Datum.IDENT and d.tp != Datum.STRING:
                raise ValueError(f"cannot use a {d.tp.name} as a spectrum column")
            col = d.val
            if len(col) < 2 or col[0] not in "msp":
                raise ValueError(f"bad spectrum column {col} - should be m, s or p followed by a wavelength")
            for w in spectrum.filters_by_wavelength:
                if SpectrumSet.Provider.colname(col[0], w) == col:
                    return valueAtWavelength(w), col[0]
            raise ValueError(f"spectrum {name} has no column {col}")

        def part(v: SpectrumValue, p: str):
            return {"m": v.v.n, "s": v.v.u, "p": v.pixels}[p]

        d = args[1]
        if d.tp == Datum.NUMBER:
            # a[name, wavelength]
            if len(args) > 2:
                raise ValueError("a third index can only be used with column names, e.g. a[0,m440,s440]")
            if not d.val.isscalar():
                raise ValueError("cannot use a vector as an index")
            return Datum(Datum.NUMBER, valueAtWavelength(float(d.val.n)).v, sources)

        # a[name, column] or a[name, column, sdcolumn]
        v, p = column(d)
        if len(args) == 2:
            # like Table, no uncertainty unless an SD column is given
            return Datum(Datum.NUMBER, Value(part(v, p)), sources)
        sv, sp = column(args[2])
        if p == "m" and sp == "s" and sv is v:
            # mean and SD of the same wavelength - that's just the stored value, so keep its DQ too
            return Datum(Datum.NUMBER, v.v, sources)
        return Datum(Datum.NUMBER, Value(part(v, p), part(sv, sp)), sources)

    #
    # Provider of a tabular view of this data
    #

    class Provider(TabularProvider):
        spectra: Dict[str, Spectrum]
        wavelengths: List[float]

        config = None

        PROVIDER_PARAMS = TaggedDictType(
            format=("Format for values",str,"separate",
                    ["separate","mean","combined"],
                    ["mean and SD are in separate columns",
                     "only the mean is shown",
                     "mean±sd in single column"]
                    ),
            orientation=("Orientation",str, "wv_cols",
                         ["wv_cols","wv_rows"],
                         ["wavelengths as columns", "wavelengths as rows"]),
        )

        def __init__(self, ss: SpectrumSet):
            self.spectra = ss.spectra

            # find all wavelengths in all spectra
            wavelengths = set()
            for roiname, spectrum in self.spectra.items():
                # filters_by_wavelength can only hold one filter per wavelength, so if
                # two filters share a wavelength we'd silently lose one of them.
                if spectrum.hasDuplicateWavelengths():
                    raise ValueError(f"Spectrum {roiname} has more than one filter at the same wavelength")
                wavelengths.update(spectrum.filters_by_wavelength.keys())
            # store the wavelengths as a sorted list
            self.wavelengths = sorted(list(wavelengths))

        @staticmethod
        def colname(prefix: str, w: float) -> str:
            """Column name for a wavelength; 440.0 gives "440" but 438.5 stays as "438.5"."""
            return f"{prefix}{w:g}"

        def getHeaders(self) -> List[str]:
            # Header will be "ROI,mwavelength,swavelength,pwavelength...."
            # for all wavelengths in all spectra.
            cols = []
            for w in self.wavelengths:
                # m, s, p prefix for each wavelength
                cols.extend([self.colname(p, w) for p in "msp"])
            return ["name"] + cols

        def __iter__(self) -> TabularIterator:
            return SpectrumSet.Provider.RowIterator(self)

        def getParams(self) -> Optional[TaggedDict]:
            # these are global settings, stored in the "tabular-provider" config section
            return SpectrumSet.Provider.config

        def setParams(self, params: TaggedDict):
            SpectrumSet.Provider.config = params
            config.save()   # this is the pcot.config module, not Provider.config

        class RowIterator(TabularIterator):
            """Iterator object for this tabular provider, generating row
            data for the table."""
            provider: SpectrumSet.Provider
            iter: Iterator[str]

            def __init__(self, provider: SpectrumSet.Provider):
                self.provider = provider
                # so we can errorcheck as we write the output dict
                self.headers = set(self.provider.getHeaders())
                # we iterate over the spectra keys (ROI names) in natural order, so "2" comes before "10"
                self.iter = iter(sorted(provider.spectra.keys(), key=naturalSortKey))

            def __next__(self) -> Dict[str, str]:
                # this will throw a StopIteration when it runs out
                roiname = next(self.iter)
                # get spectrum for the next ROI
                spectrum = self.provider.spectra[roiname]
                # this is the output dict, which will have an entry for each
                # thing in the header
                out = {}
                def write(prefix, w, v):
                    # write to the output dict, making sure the header exists
                    k = SpectrumSet.Provider.colname(prefix, w)
                    if k not in self.headers:
                        raise KeyError(f"Unknown header {k} being written to row")
                    out[k] = v
                if "name" not in self.headers:
                    raise KeyError("Unknown header name being written to row")
                out["name"] = roiname

                # each spectrum is completely different, so there could be weird stuff going on -
                # for example, spectrum A could have a different filter for wavelength X than spectrum B.
                # That's permitted, and it's why I don't try to collate the filter data (e.g. produce a
                # dict of wavelength to filter) in the constructor.

                # for each wavelength we know about
                for w in self.provider.wavelengths:
                    # look up the data - this spectrum might not have a filter at this wavelength at all
                    v: Optional[SpectrumValue] = spectrum.valueAtWavelength(w)
                    # write it to the output dict if there, otherwise write NA
                    if v is None:
                        write("m", w, "NA")
                        write("s", w, "NA")
                        write("p", w, "0")
                    else:
                        write("m", w, printable(v.v.n))
                        write("s", w, printable(v.v.u))
                        write("p", w, str(v.pixels)) # it's just an int
                return out

    def tabularProvider(self):
        """Return a tabular provider object for this spectrum set"""
        return SpectrumSet.Provider(self)

    def __str__(self):
        return self.tabularProvider().csvString()


class TabularConfigHandler(ConfigSectionHandler):
    """This class handles the persistence of the tabular provider configuration by
    hooking into the config serialisation/deserialisation system"""
    def __init__(self):
        super().__init__("tabular-provider")

    def load(self, conf):
        SpectrumSet.Provider.config = SpectrumSet.Provider.PROVIDER_PARAMS.deserialise(conf)

    def save(self) -> Any:
        return SpectrumSet.Provider.config.serialise(forceUnordered=True)

    def create(self):
        SpectrumSet.Provider.config = SpectrumSet.Provider.PROVIDER_PARAMS.create()


config.addConfigSection(TabularConfigHandler())
