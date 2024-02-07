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
from pcot.sources import SourceSet, Source, nullSource, MultiBandSource, StringExternal

# define some sources; these are immutable so it should be OK to keep them for multiple tests
s1 = Source().setExternal(StringExternal("one", "one")).setInputIdx(0)
s2 = Source().setExternal(StringExternal("two", "two")).setInputIdx(1)
s3 = Source().setExternal(StringExternal("three", "three")).setInputIdx(2)
s4 = Source().setExternal(StringExternal("four", "four")).setInputIdx(3)
s5 = Source().setExternal(StringExternal("five", "five")).setInputIdx(4)

# should give three results
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
    assert ss.brief() == "0:one"

    ss = SourceSet([s1])
    assert len(ss.sourceSet) == 1
    assert s1 in ss.sourceSet
    assert ss.brief() == "0:one"

    ss = SourceSet([s1, s2])
    assert len(ss.sourceSet) == 2
    assert s1 in ss.sourceSet
    assert s2 in ss.sourceSet
    assert ss.brief() == "0:one&1:two"

    ss = SourceSet([s1, SourceSet(s2)])
    assert len(ss.sourceSet) == 2
    assert s1 in ss.sourceSet
    assert s2 in ss.sourceSet
    assert s3 not in ss.sourceSet
    assert ss.brief() == "0:one&1:two"


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
    """Test that source set unions contain union of all subsidiary sets"""

    # make sure the union is Ok
    assert len(sourcesetunion.sourceSet) == 5
    assert s1 in sourcesetunion.sourceSet
    assert s2 in sourcesetunion.sourceSet
    assert s3 in sourcesetunion.sourceSet
    assert s4 in sourcesetunion.sourceSet
    assert s5 in sourcesetunion.sourceSet

    # just for fun, we'll remove the indices from the sources in the union
    scopy = sourcesetunion.copy()
    for s in scopy.sourceSet:
        s.setInputIdx(None)

    assert len(scopy.sourceSet) == 5
    assert scopy.brief() == "five&four&one&three&two"  # alphabetical

    # make sure the copy worked; that we're not working with the original sources
    assert s1 in sourcesetunion.sourceSet
    assert s2 in sourcesetunion.sourceSet
    assert s3 in sourcesetunion.sourceSet
    assert s4 in sourcesetunion.sourceSet
    assert s5 in sourcesetunion.sourceSet
    assert sourcesetunion.brief() == "0:one&1:two&2:three&3:four&4:five"


def test_sourcesetbrief():
    """Source set brief description test"""
    assert sourceset1withnulls.brief() == '0:one&1:two&2:three'


def test_sourcesetlong():
    """Source set long description test"""
    assert sourceset1withnulls.long() == 'SET[\n0: one\n1: two\n2: three\n]'


def test_sourcesetstr():
    """str(sourceset) should be the same as sourceset.brief()"""
    assert str(sourceset1withnulls) == sourceset1withnulls.brief()


def test_sourcesetmatches():
    """" "matches" checks to see if any source in a set matches some criterion; in this case
    we test that the index matches"""

    assert not sourceset1withnulls.matches(inp=10)
    assert sourceset1withnulls.matches(inp=1)


def test_inputsourcenames():
    """Test that input source brief() and long() are correct"""
    pcot.setup()

    source = Source().setBand(
        Filter(cwl=1000, fwhm=100, transmission=20, position="pos1", name="name1"))

    assert source.long() == "none: wavelength 1000, fwhm 100"
    assert source.brief() == "1000"  # default caption is wavelength
    assert source.brief(captionType=DocumentSettings.CAP_CWL) == "1000"
    assert source.brief(captionType=DocumentSettings.CAP_NAMES) == "name1"
    assert source.brief(captionType=DocumentSettings.CAP_POSITIONS) == "pos1"


def test_multibandsourcenames():
    """Test that multiband source brief() is correct"""
    pcot.setup()
    sources = [Source().setBand(
        Filter(cwl=(i + 1) * 1000, fwhm=100, transmission=20,
               position=f"pos{i}", name=f"name{i}")) for i in range(3)]

    # check this kind of ctor works
    ms = MultiBandSource(sources)
    assert ms.brief() == "1000|2000|3000"


def test_multibandsourcenameswithidx():
    """Test that multiband source brief() is correct when the index is set """
    pcot.setup()
    sources = [Source().setBand(
        Filter(cwl=(i + 1) * 1000, fwhm=100, transmission=20,
               position=f"pos{i}", name=f"name{i}")).setInputIdx(i + 10) for i in range(3)]

    # check this kind of ctor works
    ms = MultiBandSource(sources)
    assert ms.brief() == "10:1000|11:2000|12:3000"


def test_multibandsourcenameswithidxandext():
    """Test that multiband source brief() is correct when the index and ext is set """
    pcot.setup()
    sources = [Source().setBand(
        Filter(cwl=(i + 1) * 1000, fwhm=100, transmission=20,
               position=f"pos{i}", name=f"name{i}"))
                   .setInputIdx(i + 10)
                   .setExternal(StringExternal("ext" + str(i + 21),"extlong" + str(i + 21)))
               for i in range(3)]

    # check this kind of ctor works
    ms = MultiBandSource(sources)
    assert ms.brief() == "10:ext21:1000|11:ext22:2000|12:ext23:3000"


def test_multibandsourcenameswithidxandextandlong():
    """Test that multiband source long() is correct when the index and ext is set """
    pcot.setup()
    sources = [Source().setBand(
        Filter(cwl=(i + 1) * 1000, fwhm=100, transmission=20,
               position=f"pos{i}", name=f"name{i}"))
                   .setInputIdx(i + 10)
                   .setExternal(StringExternal("ext" + str(i + 21), "extlong" + str(i + 21)))
               for i in range(3)]

    # check this kind of ctor works
    ms = MultiBandSource(sources)
    assert ms.long() == '{\n0: SET[\n10: wavelength 1000, fwhm 100 extlong21\n]\n1: SET[\n11: wavelength 2000, fwhm 100 extlong22\n]\n2: SET[\n12: wavelength 3000, fwhm 100 extlong23\n]\n}\n'

def test_multibandsourcedunder():
    """Test that multibands act as an array of SourceSets"""

    pcot.setup()
    sources = [Source().setBand(
        Filter(cwl=(i + 1) * 1000, fwhm=100, transmission=20,
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
