"""
Test low-level source operations. Higher level operations, such as combining in expr nodes,
are tested in test_source_principles.py
"""

from typing import Optional

import pytest

import pcot
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
    """Make sure that the different valid forms of SourceSet constructor arguments work"""
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
    assert s3 not in ss.sourceSet
    assert ss.brief() == "one&two"


def test_getonlyitem():
    """Make sure that getOnlyItem() fails when we try to get the only Source in a SourceSet with
    more than one item. And that it actually works, of course."""

    ss = SourceSet([s1])
    assert ss.getOnlyItem() == s1

    ss = SourceSet([s1, s2])
    with pytest.raises(AssertionError):
        _ = ss.getOnlyItem()


def test_sourcesetdunder():
    """Test that for some purposes, a SourceSet can be interacted with directly as if one were interacting
    with the underlying set (the sourceSet member). SourceSet implements:

    * __iter__
    * __contains__
    * __len__
    """
    # check that contains() works
    ss = SourceSet([s1, s2])
    assert s1 in ss
    assert s2 in ss
    assert s3 not in ss
    assert len(ss) == 2

    # check that iteration works
    outlist = [x for x in ss]
    assert len(outlist) == 2
    assert s1 in outlist
    assert s2 in outlist

    # but we can't do sourceset[n], it's a set after all.
    with pytest.raises(TypeError):
        _ = ss[0]


def test_sourcesetunion():
    assert len(sourcesetunion.sourceSet) == 5
    assert s1 in sourcesetunion.sourceSet
    assert s2 in sourcesetunion.sourceSet
    assert s3 in sourcesetunion.sourceSet
    assert s4 in sourcesetunion.sourceSet
    assert s5 in sourcesetunion.sourceSet
    assert sourcesetunion.brief() == "five&four&one&three&two"  # alphabetical


def test_sourcesetbrief():
    """Source set brief description test"""
    assert str(sourceset1withnulls.brief()) == 'one&three&two'


def test_sourcesetlong():
    """Source set long description test"""
    assert str(sourceset1withnulls.long()) == 'SET[\nonelong\nthreelong\ntwolong\n]\n'


def test_sourcesetstr():
    """str(sourceset) should be the same as sourceset.brief()"""
    assert str(sourceset1withnulls) == sourceset1withnulls.brief()


def test_sourcesetmatches():
    """" "matches" checks to see if any source in a set matches some criterion; in this case
    we test that the name matches"""
    assert not sourceset1withnulls.matches(None, 'five')
    assert sourceset1withnulls.matches(None, 'one')


def test_inputsourcenames():
    """Test that input source brief() and long() are correct"""
    pcot.setup()

    doc = Document()
    source = InputSource(doc, inputIdx=1,
                         filterOrName=Filter(cwl=1000, fwhm=100, transmission=20, position="pos1", name="name1"))

    assert source.long() == "nullmethod: wavelength 1000"
    assert source.brief() == "nullmethod:1000"  # default caption is wavelength
    assert source.brief(captionType=DocumentSettings.CAP_CWL) == "nullmethod:1000"
    assert source.brief(captionType=DocumentSettings.CAP_NAMES) == "nullmethod:name1"
    assert source.brief(captionType=DocumentSettings.CAP_POSITIONS) == "nullmethod:pos1"


def test_multibandsourcenames():
    """Test that multiband source brief() is correct"""
    pcot.setup()
    doc = Document()
    sources = [InputSource(doc, inputIdx=1,
                           filterOrName=Filter(cwl=(i + 1) * 1000, fwhm=100, transmission=20,
                                               position=f"pos{i}", name=f"name{i}")) for i in range(3)]

    # check this kind of ctor works
    ms = MultiBandSource(sources)
    assert ms.brief() == "nullmethod:1000|nullmethod:2000|nullmethod:3000"


def test_multibandsourcedunder():
    """Test that multibands act as an array of SourceSets"""

    pcot.setup()
    doc = Document()
    sources = [InputSource(doc, inputIdx=1,
                           filterOrName=Filter(cwl=(i + 1) * 1000, fwhm=100, transmission=20,
                                               position=f"pos{i}", name=f"name{i}")) for i in range(3)]

    ms = MultiBandSource(sources)
    # check we can get the length
    assert len(ms) == 3

    # check we can iterate
    for ss, freq in zip(ms, [1000, 2000, 3000]):
        assert len(ss) == 1
        assert ss.getOnlyItem().getFilter().cwl == freq

    # check we can get the Nth item
    assert ms[1].getOnlyItem().getFilter().cwl == 2000
