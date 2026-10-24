"""
The serialisable spectrum data carried by a Datum (SpectrumSetData) and the value type it holds.
This is kept separate from the extraction code in spectrum.py, which depends on the xform machinery,
so that datumtypes can import it without a circular import.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple, List, Iterator, TYPE_CHECKING

from pcot.parameters.taggedaggregates import TaggedDict
from pcot.utils.table import printable
from pcot.utils.tabular_provider import TabularProvider, TabularIterator, naturalSortKey
from pcot.value import Value

if TYPE_CHECKING:
    from pcot.utils.spectrum import SpectrumSet


class SpectrumValue:
    """The output of the get methods in Spectrum - a single value and the number of pixels from which
    it was obtained. It can return JSON-serialisable data and be deserialised from such data."""
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


class SpectrumSetData:
    """
    This is a simplified version of a SpectrumSet which is used as a Datum object, and can be
    serialised. It doesn't carry the full filter data. Nor does it carry source data, because
    that's held in the containing Datum.

    Technically you could reconstruct a SpectrumSet from this (and sources), but I doubt it's needed.
    """
    class _Spectrum:
        """Internal class for storing the data for a single spectrum."""
        # Each filter's wavelength and fwhm (or bandwidth - might not actually be gaussian)
        filters: Dict[str, Tuple[float,float]]
        # For each filter, a spectrum value
        spectrum: Dict[str, SpectrumValue]
        # each wavelength's filter - useful in the iterator
        filter_names_by_wavelength: Dict[float, str]

        def __init__(self, filters: Dict[str, Tuple[float,float]], spectrum: Dict[str, SpectrumValue]):
            self.filters = filters
            self.spectrum = spectrum
            self.filter_names_by_wavelength = {v[0]: k for k, v in filters.items()}

        def serialise(self):
            return {
                # will convert tuples to lists
                "filters": self.filters,
                "spectrum": {k: v.serialise() for k,v in self.spectrum.items()},
            }
        @staticmethod
        def deserialise(data):
            # convert JSON lists to tuples
            f = {k: tuple(v) for k, v in data["filters"].items()}
            return SpectrumSetData._Spectrum(f, {k: SpectrumValue.deserialise(v) for k, v in data["spectrum"].items()})

    spectra: Dict[str, _Spectrum]

    def __init__(self, spectra: Dict[str, _Spectrum]):
        """Internal use only; we either deserialise or build from a SpectrumSet"""
        self.spectra = spectra

    @staticmethod
    def fromSpectrumSet(ss: 'SpectrumSet'):
        """Construct from a SpectrumSet"""
        spectra = {}
        # SpectrumSet is a dict, so we can do this.
        # k will be the ROI name (or image+ROI name). spectrum will be a Spectrum object.
        for roiname,spectrum in ss.items():
            filters = {}
            values = {}
            for filter,spectrumvalue in spectrum.data.items():
                filters[filter.name] = (filter.cwl, filter.fwhm)
                values[filter.name] = spectrumvalue
            spectra[roiname] = SpectrumSetData._Spectrum(filters, values)

        return SpectrumSetData(spectra)

    def serialise(self):
        return {
            'spectra': {k: v.serialise() for k,v in self.spectra.items()},
        }

    @staticmethod
    def deserialise(data):
        spectra = {k: SpectrumSetData._Spectrum.deserialise(v) for k,v in data["spectra"].items()}
        return SpectrumSetData(spectra)

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
            fname = spectrum.filter_names_by_wavelength.get(w)
            v = spectrum.spectrum.get(fname) if fname is not None else None
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
            for _, (w, _) in spectrum.filters.items():
                if SpectrumSetData.Provider.colname(col[0], w) == col:
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
        spectra: Dict[str, SpectrumSetData._Spectrum]
        wavelengths: List[float]

        def __init__(self, ssd: SpectrumSetData):
            self.spectra = ssd.spectra
            # find all wavelengths in all spectra
            wavelengths = set()
            for roiname, spectrum in self.spectra.items():
                # filter_names_by_wavelength can only hold one filter per wavelength, so if
                # two filters share a wavelength we'd silently lose one of them.
                if len(spectrum.filter_names_by_wavelength) != len(spectrum.filters):
                    raise ValueError(f"Spectrum {roiname} has more than one filter at the same wavelength")
                for filter in spectrum.filters.values():
                    wavelengths.add(filter[0]) # add wavelength as float
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
            return SpectrumSetData.Provider.RowIterator(self)

        def getParams(self) -> Optional[TaggedDict]:
            return None  # not parameterisable yet - TODO



        class RowIterator(TabularIterator):
            """Iterator object for this tabular provider, generating row
            data for the table."""
            provider: SpectrumSetData.Provider
            iter: Iterator[str]

            def __init__(self, provider: SpectrumSetData.Provider):
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
                    k = SpectrumSetData.Provider.colname(prefix, w)
                    if k not in self.headers:
                        raise KeyError(f"Unknown header {k} being written to row")
                    out[k] = v
                if "name" not in self.headers:
                    raise KeyError("Unknown header name being written to row")
                out["name"] = roiname

                # each spectrum is completely different, so there could be weird stuff going on -
                # for example, spectrum A could have a different filter for wavelength X than spectrum B.
                # That's permitted, and it's why I don't try to collate the filter data (e.g. produce a
                # dict of wavelength to filter name) in the constructor.

                # for each wavelength we know about
                for w in self.provider.wavelengths:
                    # get the appropriate filter name from this spectrum, which might not have
                    # a filter at this wavelength at all
                    fname = spectrum.filter_names_by_wavelength.get(w)
                    # look up the data
                    v: Optional[SpectrumValue] = spectrum.spectrum.get(fname) if fname is not None else None
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
        return SpectrumSetData.Provider(self)

    def __str__(self):
        return self.tabularProvider().csvString()
