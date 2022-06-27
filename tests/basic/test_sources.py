from typing import Optional

from pcot.document import Document
from pcot.documentsettings import DocumentSettings
from pcot.filters import Filter
from pcot.sources import SourceSet, Source, nullSource, InputSource, MultiBandSource


class SimpleTestSource(Source):
    """Only used in this test suite"""

    def __init__(self, name):
        self.name = name

    def brief(self, captionType=None) -> Optional[str]:
        return self.name

    def long(self) -> Optional[str]:
        return self.name + 'long'

    def copy(self):
        """not actually a copy, but this is immutable anyway"""
        return self

    def matches(self, inp, bandNameOrCWL, hasBand):
        # very crude check here, we're ignoring inputIdx.
        return bandNameOrCWL == self.name

    def serialise(self):
        return 'testsource', self.name


# define some sources; these are immutable so it should be OK to keep them for multiple tests
s1 = SimpleTestSource("one")
s2 = SimpleTestSource("two")
s3 = SimpleTestSource("three")
s4 = SimpleTestSource("four")
s5 = SimpleTestSource("five")
s6 = SimpleTestSource("six")

sourceset1 = SourceSet([s1, s2, s3])
# this should produce FIVE results when unioned with the above; note the overlap with s1
sourceset2 = SourceSet([s4, s5, s1])
sourceset1withnulls = SourceSet([s1, s2, s3, nullSource])
# should have five sources.
sourcesetunion = SourceSet([sourceset1, sourceset2])


def test_sourcesetctors():
    ss = SourceSet(s1)
    assert len(ss.sourceSet) == 1
    assert s1 in ss.sourceSet
    assert ss.brief() == "one"

    ss = SourceSet([s1])
    assert len(ss.sourceSet) == 1
    assert s1 in ss.sourceSet
    assert ss.brief() == "one"

    ss = SourceSet([s1, s2])
    assert len(ss.sourceSet) == 2
    assert s1 in ss.sourceSet
    assert s2 in ss.sourceSet
    assert ss.brief() == "one&two"

    ss = SourceSet([s1, SourceSet(s2)])
    assert len(ss.sourceSet) == 2
    assert s1 in ss.sourceSet
    assert s2 in ss.sourceSet
    assert ss.brief() == "one&two"


def test_sourcesetunion():
    assert len(sourcesetunion.sourceSet) == 5
    assert s1 in sourcesetunion.sourceSet
    assert s2 in sourcesetunion.sourceSet
    assert s3 in sourcesetunion.sourceSet
    assert s4 in sourcesetunion.sourceSet
    assert s5 in sourcesetunion.sourceSet
    assert sourcesetunion.brief() == "five&four&one&three&two"  # alphabetical



def test_sourcesetbrief():
    assert str(sourceset1withnulls.brief()) == 'one&three&two'


def test_sourcesetlong():
    assert str(sourceset1withnulls.long()) == 'SET[\nonelong\nthreelong\ntwolong\n]\n'


def test_sourcesetstr():
    assert str(sourceset1withnulls) == '(none)&one&three&two'


def test_sourcesetmatches():
    # "matches" checks to see if any source in a set matches some criterion. Our test source
    # only has the name.
    assert not sourceset1withnulls.matches(None, 'five')
    assert sourceset1withnulls.matches(None, 'one')


def test_inputsourcenames():
    doc = Document()
    source = InputSource(doc, inputIdx=1,
                         filterOrName=Filter(cwl=1000, fwhm=100, transmission=20, position="pos1", name="name1"))

    assert source.long() == "nullmethod: wavelength 1000"
    assert source.brief() == "nullmethod:1000"  # default caption is wavelength
    assert source.brief(captionType=DocumentSettings.CAP_CWL) == "nullmethod:1000"
    assert source.brief(captionType=DocumentSettings.CAP_NAMES) == "nullmethod:name1"
    assert source.brief(captionType=DocumentSettings.CAP_POSITIONS) == "nullmethod:pos1"


def test_multibandsourcenames():
    doc = Document()
    sources = [InputSource(doc, inputIdx=1,
                           filterOrName=Filter(cwl=(i + 1) * 1000, fwhm=100, transmission=20,
                                               position=f"pos{i}", name=f"name{i}")) for i in range(3)]

    # check this kind of ctor works
    ms = MultiBandSource(sources)
    assert ms.brief() == "nullmethod:1000|nullmethod:2000|nullmethod:3000"
