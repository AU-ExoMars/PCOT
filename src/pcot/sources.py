"""
New source tracking system - each Datum will have a source describing which input it comes from,
and each input will know how to generate useful information from that source.
"""
from typing import Optional, List, Union

from pcot.document import Document
from pcot.filters import Filter
from pcot.inputs import Input


class Source:
    """The base class for sources, with the exception of MultiBandSource which is only used in images."""
    pass


class SingleSource(Source):
    """A basic source for a single band of an image or a non-image value. Designed so that two Source objects
    with the same document, filter and input index are the same."""

    filter: Optional[Filter]    # if this is an image band, reference to the filter. Else None.
    doc: Document               # which document I'm associated with
    inputIdx: int               # the index of the input within the document
    input: Input                # the actual input object

    def __init__(self, doc, inputIdx, filt=None):
        self.filter = filt
        self.doc = doc
        self.inputIdx = inputIdx
        self.input = self.doc.inputMgr.inputs[inputIdx]
        # this is used for hashing and equality - should be the same for two identical sources
        filtCwl = self.filter.cwl if self.filter else 'none'
        self._uniqid = f"{id(self.doc)}/{self.inputIdx}/{filtCwl}"

    def __eq__(self, other: 'SingleSource'):
        return self._uniqid == other._uniqid

    def __hash__(self):
        return hash(self._uniqid)


class SourceSet(Source):
    """This is a combination of sources which have produced a single-band datum - could be a band of an
    image or some other type"""

    def __init__(self, ss=[]):
        """The constructor takes a list of sources and source sets, and generates a new source set which is
        a union of all of them"""
        result = set()
        for x in ss:
            if isinstance(x, SourceSet):
                result |= x.sourceSet
            elif isinstance(x, SingleSource):
                result.add(x)
            else:
                raise Exception(f"Bad argument to source set constructor: {type(x)}")
        self.sourceSet = result


class MultiBandSource:
    """This is an array of sources for a single image with multiple bands; each source is indexed by the band"""

    sources: List[Source]

    def __init__(self, s=[]):
        self.sources = s

    def add(self, s):
        self.sources.add(s)


