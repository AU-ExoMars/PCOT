"""
New source tracking system - each Datum will have a source describing which input it comes from,
and each input will know how to generate useful information from that source.
"""
import math
from abc import ABC, abstractmethod
from typing import Optional, List, Set, SupportsFloat, Union, Iterable, Any, Tuple

from pcot.dataformats.pds4 import PDS4Product
from pcot.filters import Filter


class SourcesObtainable(ABC):
    """Interface for all sources; we can get a set of all sources from this"""

    @abstractmethod
    def getSources(self) -> 'SourceSet':
        """get a SourceSet of all sources"""
        pass


class Source(SourcesObtainable):
    """The base class for sources, with the exception of MultiBandSource which is only used in images.
    This is abstract - the absolute minimum functionality is in NullSource."""

    @abstractmethod
    def copy(self):
        """Return a reasonably deep copy of the source"""
        pass

    def matches(self, inp, bandNameOrCWL, hasBand):
        """Returns true if the input index matches this source (if not None) and the band matches this source (if not none).
        None values are ignored, so passing "inp" of None will mean the input index is not checked.
        Default implementation matches nothing."""
        return False

    def getFilter(self):
        """return any filter"""
        return None

    def getSources(self):
        """return a set of all sources"""
        return SourceSet(self)

    def getPDS4(self):
        """If a PDS4 product, get its PDS4Product - this will have the LID"""
        return None

    @abstractmethod
    def brief(self, captionType=0) -> Optional[str]:
        """Return a brief string to be used in captions, etc. If null, is filtered out"""
        pass

    @abstractmethod
    def long(self) -> Optional[str]:
        """Return a longer text, possibly with line breaks"""
        pass

    @abstractmethod
    def serialise(self) -> Tuple[str, Any]:
        """return type and serialisation data - deserialisation is done in SourceSet"""
        pass


class _NullSource(Source):
    """This is for "sources" where there isn't a source, the data has come from inside the program.
    Typically this will get filtered out when we print the sources. Probably best to use nullSource and nullSourceSet
    objects declared at the end of this module"""

    def brief(self, captionType=0) -> Optional[str]:
        """return a brief string for use in captions - this will just return None, which will
        be filtered out when used in such captions."""
        return None

    def long(self) -> Optional[str]:
        """See above - None gets filtered out of text information"""
        return None

    def copy(self):
        """not actually a copy, but this is immutable anyway"""
        return self

    def serialise(self):
        return 'nullsource', None


class InputSource(Source):
    """A basic source for a single band of an image or a non-image value.
    This is for things which actually come from an Input. Designed so that two Source objects
    with the same document, filter and input index are the same."""

    # if this is an filtered image band, reference to the filter; else a string for the band name
    filterOrName: Union[Filter, str]
    doc: 'Document'  # which document I'm associated with
    inputIdx: int  # the index of the input within the document
    input: 'Input'  # the actual input object
    pds4: PDS4Product  # any PDS4 data

    def __init__(self, doc, inputIdx, filterOrName, pds4: PDS4Product = None):
        """This takes a document, inputIdx, and either a filter or a name"""
        self.filterOrName = filterOrName
        self.doc = doc
        self.inputIdx = inputIdx
        self.input = doc.inputMgr.inputs[inputIdx]
        self.pds4 = pds4
        # this is used for hashing and equality - should be the same for two identical sources
        filtID = self.filterOrName.cwl if isinstance(self.filterOrName, Filter) else self.filterOrName
        self._uniqid = f"{id(self.doc)}/{self.inputIdx}/{filtID}"

    def getFilter(self):
        """return the filter if there really is one, else none"""
        return self.filterOrName if isinstance(self.filterOrName, Filter) else None

    def getPDS4(self):
        return self.pds4

    def copy(self):
        return InputSource(self.doc, self.inputIdx, self.filterOrName)

    def __eq__(self, other: 'InputSource'):
        return self._uniqid == other._uniqid

    def __hash__(self):
        return hash(self._uniqid)

    def __str__(self):
        """Return a full internal string representation, used in debugging"""
        return f"SOURCE-{self._uniqid}"

    def brief(self, captionType=0) -> Optional[str]:
        """return a brief string representation, used in image captions"""
        inptxt = self.input.brief()
        if isinstance(self.filterOrName, Filter):
            if captionType == 0:  # 0=Position
                cap = self.filterOrName.position
            elif captionType == 1:  # 1=Name
                cap = self.filterOrName.name
            elif captionType == 2:  # 2=Wavelength
                cap = int(self.filterOrName.cwl)
            else:
                cap = f"CAPBUG-{captionType}"  # if this appears captionType is out of range.
            return f"{inptxt}:{cap}"
        else:
            return f"{inptxt}:{self.filterOrName}"

    def long(self):
        inptxt = self.input.long()
        if isinstance(self.filterOrName, Filter):
            s = f"{inptxt}: wavelength {int(self.filterOrName.cwl)}"
        else:
            s = f"{inptxt}: band {self.filterOrName}"
        if self.getPDS4():
            s += f" {self.getPDS4().lid}"
        return s

    def matches(self, inp, filterNameOrCWL, hasFilter):
        """return true if the source matches ALL the non-None criteria"""
        if inp and inp != self.inputIdx:
            return False
        if hasFilter is not None:
            if hasFilter and not self.getFilter():
                return False
            if not hasFilter and self.getFilter():
                return False
        if filterNameOrCWL:
            if isinstance(filterNameOrCWL, str):
                name = self.filterOrName.name if isinstance(self.filterOrName, Filter) else self.filterOrName
                pos = self.filterOrName.position if isinstance(self.filterOrName, Filter) else None
                if name != filterNameOrCWL and pos != filterNameOrCWL:
                    return False
            elif isinstance(filterNameOrCWL, SupportsFloat):  # this is OK, SupportsFloat is a runtime chkable protocol
                if not isinstance(self.filterOrName, Filter) \
                        or not math.isclose(filterNameOrCWL, self.filterOrName.cwl):
                    return False
        return True

    def serialise(self):
        # deserialisation is done in SourceSet

        if isinstance(self.filterOrName,Filter):
            filtorname = ('filter', self.filterOrName.serialise())
        elif isinstance(self.filterOrName, str):
            filtorname = ('name', self.filterOrName)
        else:
            raise Exception(f"cannot serialise a {type(self.filterOrName)} as a filter")

        d = {
            'filtorname': filtorname,
            'inputidx': self.inputIdx,
            'pds4': None if self.pds4 is None else self.pds4.serialise()
        }
        return 'inputsource', d


class SourceSet(SourcesObtainable):
    """This is a combination of sources which have produced a single-band datum - could be a band of an
    image or some other type"""

    sourceSet: Set[Source]  # the underlying set of sources

    def __init__(self, ss: Union[Source, 'SourceSet', Iterable[Union[Source, 'SourceSet']]] = ()):
        """The constructor takes a collection of sources and source sets, or just one, and generates a new source
        set which is  a union of all of them"""
        if isinstance(ss, Source):
            result = {ss}
        elif isinstance(ss, SourceSet):
            result = ss
        elif isinstance(ss, Iterable):
            result = set()
            for x in ss:
                if isinstance(x, SourceSet):
                    result |= x.sourceSet
                elif isinstance(x, Source):
                    result.add(x)
                elif isinstance(x, SourcesObtainable):
                    result |= x.getSources()
                else:
                    raise Exception(f"Bad list argument to source set constructor: {type(x).__name__}")
        else:
            raise Exception(f"Bad argument to source set constructor: {type(ss).__name__}")

        self.sourceSet = result

    def add(self, other: 'SourceSet'):
        """add a source set to this one (i.e. this source set will become a union of irself and the other)"""
        self.sourceSet |= other.sourceSet

    def copy(self):
        return SourceSet([x.copy() for x in self.sourceSet])

    def __str__(self):
        """internal text description; uses (none) for null sources"""
        return "&".join([str(x) if x else "(none)" for x in self.sourceSet])

    def brief(self, captionType=0):
        """external (user-facing) text description, skips null sources"""
        x = [x.brief(captionType) for x in self.sourceSet]
        return "&".join(sorted([s for s in x if s]))

    def long(self):
        x = [x.long() for x in self.sourceSet]
        lst = "\n".join(sorted([s for s in x if s]))
        return f"SET[\n{lst}\n]\n"

    def matches(self, inp=None, filterNameOrCWL=None, single=False, hasFilter=None):
        """Returns true if ANY source in the set matches ALL the criteria"""
        if single and len(self.sourceSet) > 1:  # if required, ignore this set if it's not from a single source
            return False
        return any([x.matches(inp, filterNameOrCWL, hasFilter) for x in self.sourceSet])

    def getSources(self):
        return self

    def serialise(self):
        # store each source in set with its type, as a list of tuples
        return [x.serialise() for x in self.sourceSet]

    @classmethod
    def deserialise(cls, lst, document) -> 'SourceSet':
        out = []
        for tp,d in lst:
            if tp == 'nullsource':
                v = nullSource
            elif tp == 'inputsource':
                pds4 = None if d['pds4'] is None else PDS4Product.deserialise(d['pds4'])
                forntype, filtdata = d['filtorname']
                if forntype == 'filter':
                    filt = Filter.deserialise(filtdata)
                else:
                    filt = filtdata

                v = InputSource(document,
                                d['inputidx'],
                                filt,
                                pds4)
            else:
                raise Exception(f"Bad type in sourceset serialisation data: {tp}")
            out.append(v)
        return cls(out)


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
                    # add the source for that channel to the set
                    newSet.add(mbs.sourceSets[i])
            sets.append(newSet)
        return cls(sets)

    def add(self, s):
        """add a band's sources to this one"""
        self.sourceSets.append(s)

    def copy(self):
        """Make a fairly deep copy of the source sets"""
        return MultiBandSource([ss.copy() for ss in self.sourceSets])

    def search(self, filterNameOrCWL=None, inp=None, single=False, hasFilter=None):
        """Given some criteria, returns a list of indices of bands whose source sets contain a member which matches
            ALL those criteria:
            filtNameOrCWL : value must match the name, position or wavelength of a filter
            inp : value must match input index
            single : there must only be a single source in the set
        """
        out = []
        for i, s in enumerate(self.sourceSets):
            if s.matches(inp, filterNameOrCWL, single, hasFilter):
                out.append(i)
        return out

    def brief(self):
        """Brief text description - note, may not be used for captions."""
        out = [s.brief() for s in self.sourceSets]
        return "|".join(out)

    def long(self):
        txts = [f"{i}: {s.long()}" for i, s in enumerate(self.sourceSets)]
        s = "\n".join(txts)
        return "{\n" + s + "\n}\n"

    def getSources(self):
        """Merge all the bands' source sets into a single set (used in, for example, making a greyscale
        image, or any calculation where all bands have input)"""
        return set().union(*[s.sourceSet for s in self.sourceSets])

    def serialise(self):
        return [x.serialise() for x in self.sourceSets]

    @classmethod
    def deserialise(cls, lst, document):
        lst = [SourceSet.deserialise(x, document) for x in lst]
        return cls(lst)


# use these to avoid the creation of lots of identical objects

nullSource = _NullSource()
nullSourceSet = SourceSet(nullSource)
