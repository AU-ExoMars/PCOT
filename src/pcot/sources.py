"""
New source tracking system - each Datum will have a source describing which input it comes from,
and each input will know how to generate useful information from that source.
"""
import math
from abc import ABC, abstractmethod
from typing import Optional, List, Set, SupportsFloat, Union, Iterable, Any, Tuple, Dict, Callable

from pcot.documentsettings import DocumentSettings
from pcot.cameras.filters import Filter
from pcot.parameters.taggedaggregates import Maybe


class SourcesObtainable(ABC):
    """Interface for all sources; we can get a set of all sources from this"""

    @abstractmethod
    def getSources(self) -> 'SourceSet':
        """get a SourceSet of all sources"""
        pass


class External:
    """An external source, such as a file or a PDS4 product, so we can
    print information about it in the long descriptor. The most basic
    subclass of this is StringExternal, which just has a string label.
    """

    def __init__(self):
        """Initialise"""
        pass

    def brief(self):
        """Get a brief description of where the data comes from. Very short indeed, like "PDS4" or "ENVI" """
        pass

    def long(self):
        """Get a longer description of where the data comes from"""
        pass

    def debug(self):
        """Get a debug string, for testing"""
        pass

    def serialise(self):
        """Serialise to a tuple including the type"""
        pass

    @staticmethod
    def deserialise(tup: Tuple[str, Any]):
        """Deserialise from a tuple"""
        t, data = tup

        if t == 'external':  # this is a string external, really two strings.
            e = StringExternal(data[0], data[1])
        elif t == 'pds4':
            from pcot.dataformats.pds4 import PDS4External
            e = PDS4External.deserialise(data)
        else:
            raise ValueError(f"Unknown external source type {t} in Source External deserialise")
        return e


class StringExternal(External):
    """The most basic external type - just a string label we can add to sources to give
    more information"""
    _brief: str
    _long: str

    def __init__(self, brief: str, long: str):
        super().__init__()
        self._brief = brief
        self._long = long

    def brief(self):
        return self._brief

    def long(self):
        return self._long

    def debug(self):
        """Get a debug string, for testing - it's OK for this to just be the brief string"""
        return self._brief

    def serialise(self):
        return 'external', (self._brief, self._long)


class Source(SourcesObtainable):
    """A source object describing where a piece of data comes from. These can get combined into source sets
    if a datum comes from more than one source. What the source actually is depends on which members are
    not None:

    - band: if the source is an image, this is the Filter object or just a string if there is no filter (e.g.
        "R" for red)
    - external: if the source is from outside PCOT, this object has a getstr() method to describe it.
    - inputIdx: if the source is an input, this is the index of the input.
    - purpose: if not None, this is a secondary source which will not match(), so won't interfere with searches
        for name or wavelength. For example, we could have a single main source (where this is None) and lots
        of others used for calibration, but the main source would still be considered the only source for a band
        most of the time (e.g. ImageCube's filter() method and methods that rely on it, and SourceSet's getOnlyItem)

    If all of these are None, it's a "null source" often used for dummy data.
    """

    band: Union[Filter, None, str]  # if an image this could be either a filter or a band name (e.g. "R" for red)
    external: Optional[External]  # an external source object (file or pds4 product) or None
    inputIdx: Optional[int]  # the index of the input, if this is an input source
    purpose: Optional[str]    # the purpose of the source (see the docstring) - usually None

    def __init__(self):
        """Initialise to a null source"""
        self.band = None
        self.external = None
        self.inputIdx = None
        self.purpose = None

    def isMain(self):
        """Returns true if this is a main source - i.e. not a secondary source"""
        return self.purpose is None

    def setSecondaryPurpose(self, s):
        """Set the purpose of the source. This is used to indicate that this source is not the main source for a band,
        but is still useful for calibration or other purposes. The purpose is not used in matches() or brief()"""
        self.purpose = s
        return self

    # fluent setters
    def setBand(self, b: Union[Filter, str, None]):
        """Set the band for sources which come from images. If None, it's either not an image or it's mono."""
        self.band = b
        return self

    def setExternal(self, e: Optional[External]):
        """Set the external source"""
        self.external = e
        return self

    def setInputIdx(self, i: Optional[int]):
        """Set the input index"""
        self.inputIdx = i
        return self

    def copy(self):
        """Return a reasonably deep copy of the source"""
        return Source().setBand(self.band) \
            .setExternal(self.external) \
            .setInputIdx(self.inputIdx) \
            .setSecondaryPurpose(self.purpose)

    def matches(self, inp, bandNameOrCWL, hasBand):
        """Returns true if the input index matches this source (if not None) and the band matches this source (if not none).
        None values are ignored, so passing "inp" of None will mean the input index is not checked.
        """
        if self.purpose:
            # don't match if the purpose is set - it's a secondary source
            return False
        if hasBand is not None:
            if hasBand and not self.band:
                return False
            if not hasBand and self.band:
                return False
        if inp is not None:
            if self.inputIdx != inp:
                return False
        if bandNameOrCWL is not None:
            if isinstance(bandNameOrCWL, str):
                name = self.band.name if isinstance(self.band, Filter) else self.band
                pos = self.band.position if isinstance(self.band, Filter) else None
                if name != bandNameOrCWL and pos != bandNameOrCWL:
                    return False
            elif isinstance(bandNameOrCWL, SupportsFloat):  # this is OK, SupportsFloat is a runtime chkable protocol
                if not isinstance(self.band, Filter) \
                        or not math.isclose(bandNameOrCWL, self.band.cwl):
                    return False
        return True

    def isNull(self):
        """Returns true if this is a null source"""
        return self.band is None and self.external is None and self.inputIdx is None

    def getSources(self):
        """return a set of all sources"""
        return SourceSet(self)

    def getFilter(self):
        """check that a the source is an image with a filter, and return the filter if so. Otherwise return None"""
        return self.band if isinstance(self.band, Filter) else None

    def debug(self):
        """Return a string for debugging and tests - we don't use brief() here, because it's possible that brief()
        could change a lot and we don't want to have to update all tests when it does."""

        inpidx = str(self.inputIdx) if self.inputIdx is not None else "NI"
        ext = self.external.debug() if self.external else "NE"
        band = self.band.getCaption(DocumentSettings.CAP_CWL) if isinstance(self.band, Filter) else self.band
        if band is None:
            band = "NB"

        return ",".join([inpidx, ext, band])

    def brief(self, captionType=DocumentSettings.CAP_DEFAULT) -> Optional[str]:
        """Return a brief string to be used in captions, etc. If null, is filtered out"""

        # The brief consists of three elements separated by colons:
        # - the input index, if not None
        # - the external source, if not None
        # - the band, if not None

        lst = [self.inputIdx,
               self.external.brief() if self.external else None,
               self.band.getCaption(captionType) if isinstance(self.band, Filter) else self.band]

        # filter out the Nones and convert to strings
        lst = [str(x) for x in lst if x is not None]
        # and return the elements joined by colons
        return ":".join(lst)

    def long(self) -> Optional[str]:
        """Return a longer text, possibly with line breaks"""
        s = f"{self.purpose} " if self.purpose else ""

        inptxt = f"{self.inputIdx}" if self.inputIdx is not None else "none"
        if self.band is None:
            s += f"{inptxt}:"
        elif isinstance(self.band, Filter):
            s += f"{inptxt}: {self.band.sourceDesc()}"
        else:
            s += f"{inptxt}: band {self.band}"
        if self.external is not None:
            s += f" {self.external.long()}"
        return s

    def serialise(self) -> Dict[str, Any]:
        """return type and serialisation data"""
        return {
            'band': self.band.serialise() if isinstance(self.band, Filter) else self.band,
            'external': self.external.serialise() if self.external else None,
            'inputIdx': self.inputIdx,
            'purpose': self.purpose
        }

    @staticmethod
    def deserialise(d: Dict[str, Any]):
        """Deserialise from a dictionary"""
        import pcot.ui as ui
        if isinstance(d, List):
            # legacy format
            ui.log("Legacy format for sources not supported - please Run All to regenerate")
            return Source().setExternal(StringExternal("ERROR", "Legacy format for sources not supported"))

        b = Filter.deserialise(d['band']) if isinstance(d['band'], list) else d['band']
        e = External.deserialise(d['external']) if d['external'] else None
        p = d.get('purpose', None)
        i = d['inputIdx']
        return Source().setBand(b).setExternal(e).setInputIdx(i).setSecondaryPurpose(p)

    def __eq__(self, other):
        if not isinstance(other, Source):
            return False
        return self.band == other.band and self.external == other.external and self.inputIdx == other.inputIdx and \
            self.purpose == other.purpose

    def __hash__(self):
        return hash(self.long())


class SourceSet(SourcesObtainable):
    """This is a combination of sources which have produced a single-band datum - could be a band of an
    image or some other type"""

    sourceSet: Set[Source]      # the underlying set of sources

    def __init__(self, ss: Union[Source, 'SourceSet', Iterable[Union[Source, 'SourceSet', SourcesObtainable]]] = ()):
        """The constructor takes a collection of sources and source sets, or just one, and generates a new source
        set which is  a union of all of them"""
        if isinstance(ss, Source):
            result = {ss}
        elif isinstance(ss, SourceSet):
            result = ss.sourceSet
        elif isinstance(ss, Iterable):
            result = set()
            for x in ss:
                if isinstance(x, SourcesObtainable):
                    result |= x.getSources().sourceSet
                else:
                    raise Exception(f"Bad list argument to source set constructor: {type(x).__name__}")
        else:
            raise Exception(f"Bad argument to source set constructor: {type(ss).__name__}")

        self.sourceSet = result
        self.stripNullSources()

    def stripNullSources(self):
        """Removes null sources from the set and return self"""
        self.sourceSet = {x for x in self.sourceSet if x is not None and not x.isNull()}
        return self

    def add(self, other: 'SourceSet'):
        """add a source set to this one (i.e. this source set will become a
        union of irself and the other). Returns self"""
        self.sourceSet |= other.sourceSet
        self.stripNullSources()
        return self

    def visit(self, f: Callable[[Source], None]):
        """Apply a function to each source in the set"""
        for s in self.sourceSet:
            f(s)
        return self

    def copy(self):
        """return a new set with a copy of all sources"""
        return SourceSet([x.copy() for x in self.sourceSet])

    def __str__(self):
        """internal text description; uses (none) for null sources and skips dups"""
        strdata = [x.brief() for x in self.sourceSet]
        strdata = sorted([x if x else "(none)" for x in strdata])
        return "&".join(list(dict.fromkeys(strdata)))

    def brief(self, captionType=DocumentSettings.CAP_DEFAULT):
        """external (user-facing) text description, skips null sources and duplicates"""
        x = list(dict.fromkeys([x.brief(captionType) for x in self.sourceSet]))
        return "&".join(sorted([s for s in x if s]))

    def debug(self):
        """debugging text description"""
        x = [x.debug() for x in self.sourceSet]
        return " & ".join(sorted([s for s in x if s]))

    def long(self):
        x = [x.long() for x in self.sourceSet]
        lst = "\n".join(sorted([s for s in x if s]))
        return f"SET[\n{lst}\n]"

    def matches(self, inp=None, filterNameOrCWL=None, single=False, hasFilter=None, all_match=False):
        """Returns true if ANY main source in the set matches ALL the criteria; or if all_match is true if ALL
        sources match the criteria:
        inp: input index
        filterNameOrCWL: either a filter name or a centre wavelength
        single: set must be a single item
        hasFilter: set must have a filter
        all_match: all items in set must match
        """
        mains = [x for x in self.sourceSet if x.isMain()]
        if single and len(mains) > 1:  # if required, ignore this set if it's not from a single source
            return False
        if len(mains) == 0:  # if there isn't an item there can't be a match (note: all([]) == True, dammit)
            return False
        smatches = [x.matches(inp, filterNameOrCWL, hasFilter) for x in mains]

        if all_match:
            return all(smatches)
        else:
            return any(smatches)

    ### wrappers around dunder methods of set for convenience. Could inherit set, but that's messy.
    def __len__(self):
        return len(self.sourceSet)

    def __iter__(self):
        return self.sourceSet.__iter__()

    def __contains__(self, item):
        return self.sourceSet.__contains__(item)

    def __eq__(self, other):
        if not isinstance(other, SourceSet):
            return False
        return self.sourceSet == other.sourceSet

    def getOnlyItem(self):
        """return singleton item, excluding secondary sources"""
        x = [x for x in self.sourceSet if x.isMain()]
        assert len(x) == 1
        e, = x
        return e

    def getFilters(self):
        """Return a set of all the filters used by this sourceSet in main sources"""
        return {x.band for x in self.sourceSet if isinstance(x.band, Filter) and x.isMain()}

    def getSources(self):
        """implements SourcesObtainable"""
        return self

    def serialise(self):
        # store each source in set with its type, as a list of tuples
        return [x.serialise() for x in self.sourceSet]

    @classmethod
    def deserialise(cls, lst) -> 'SourceSet':
        ss = [Source.deserialise(x) for x in lst]
        return cls(ss)


class MultiBandSource(SourcesObtainable):
    """This is an array of source sets for a single image with multiple bands; each set  is indexed by the band"""

    sourceSets: List[SourceSet]  # life is much simpler if this is public.

    def __init__(self, ss: List[Union[SourceSet, Source]] = ()):
        # turn any sources into single-element source sets
        ss = [s if isinstance(s, SourceSet) else SourceSet(s) for s in ss]
        self.sourceSets = ss

    @classmethod
    def createEmptySourceSets(cls, count):
        """Alternative constructor for when no source sets are provided: this will create an empty source set
        for each channel, given the number of channels."""
        return cls([SourceSet() for _ in range(count)])

    @classmethod
    def createBandwiseUnion(cls, lst: List['MultiBandSource']):
        """For each MultiBandSource in the list, create a new one which is a band-wise union of all of them;
        the number of bands is equal to the maximum band count of the MBSs in the list."""
        numChannels = max([len(x.sourceSets) for x in lst])  # yes, I'm using 'band' and 'channel' interchangeably.
        sets = []  # a list of SourceSets we're going to build
        for i in range(numChannels):
            # for each channel work on a new set
            newSet = SourceSet()
            for mbs in lst:
                # for each input MultiBandSource
                if i < len(mbs.sourceSets):
                    xx = mbs.sourceSets[i]
                    # add the source for that channel to the set
                    newSet.add(xx)
            sets.append(newSet)
        return cls(sets)

    def add(self, s):
        """add a band's sources to this one. Returns self."""
        self.sourceSets.append(s)
        return self

    def addSetToAllBands(self, s: SourceSet):
        """Given a SourceSet, add that set as a source to all bands. Returns self"""
        for ss in self.sourceSets:
            ss.add(s)
        return self

    def copy(self):
        """Make a fairly deep copy of the source sets"""
        return MultiBandSource([ss.copy() for ss in self.sourceSets])

    def visit(self, f: Callable[[SourceSet], None]):
        """Apply a function to each source set"""
        for ss in self.sourceSets:
            f(ss)
        return self

    def search(self, filterNameOrCWL=None, inp=None, single=False, hasFilter=None):
        """Given some criteria, returns a list of indices of bands whose source sets contain a member which matches
            ALL those criteria:
            filtNameOrCWL : value must match the name, position or wavelength of a filter
            inp : value must match input index
            single : there must only be a single source in the set
        """
        out = []

        # here we process things like "$_5" to get band 5 explicitly. It's possibly a historical artifact?
        if isinstance(filterNameOrCWL, str) and filterNameOrCWL.startswith('_'):
            band = filterNameOrCWL[1:]
            try:
                band = int(band)
            except ValueError:
                return []
            if band >= len(self.sourceSets):
                return []
            return [band]

        # otherwise we do the search as usual
        for i, s in enumerate(self.sourceSets):
            if s.matches(inp, filterNameOrCWL, single, hasFilter):
                out.append(i)
        return out

    def brief(self):
        """Brief text description - note, may not be used for captions. Note the "|" separator for separate bands."""
        out = [s.brief() for s in self.sourceSets]
        return "|".join(out)

    def debug(self):
        """Debug text description"""
        out = [s.debug() for s in self.sourceSets]
        return " | ".join(out)

    def long(self):
        txts = [f"{i}: {s.long()}" for i, s in enumerate(self.sourceSets)]
        s = "\n".join(txts)
        return "{\n" + s + "\n}\n"

    def getSources(self):
        """Merge all the bands' source sets into a single set (used in, for example, making a greyscale
        image, or any calculation where all bands have input)"""
        return SourceSet(set().union(*[s.sourceSet for s in self.sourceSets]))

    def getFiltersByBand(self):
        """Return a list of sets of filters for each band"""
        return [x.getFilters() for x in self.sourceSets]

    def serialise(self):
        return [x.serialise() for x in self.sourceSets]

    @classmethod
    def deserialise(cls, lst):
        lst = [SourceSet.deserialise(x) for x in lst]
        return cls(lst)

    def __len__(self):
        return len(self.sourceSets)

    def __iter__(self):
        return self.sourceSets.__iter__()

    def __contains__(self, item):
        return item in self.sourceSets

    def __getitem__(self, item):
        return self.sourceSets[item]


# Standard null sources: use these to avoid the creation of lots of identical objects
# when you just want a null source without filter.

nullSource = Source()
nullSourceSet = SourceSet(nullSource)
