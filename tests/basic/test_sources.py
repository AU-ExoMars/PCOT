from typing import Optional

from pytest import fixture

from pcot.datum import Datum
from pcot.sources import SourceSet, Source


class TestSource(Source):
    """Only used in this test suite"""

    def __init__(self, name):
        self.name = name

    def brief(self, captionType=None) -> Optional[str]:
        return self.name

    def long(self) -> Optional[str]:
        return self.name

    def copy(self):
        """not actually a copy, but this is immutable anyway"""
        return self

    def serialise(self):
        return 'testsource', self.name


# define some sources; these are immutable so it should be OK to keep them for multiple tests
s1 = TestSource("one")
s2 = TestSource("two")
s3 = TestSource("three")
s4 = TestSource("four")
s5 = TestSource("five")
s6 = TestSource("six")


@fixture
def sourceset1():
    return SourceSet([s1, s2, s3])


@fixture
def sourceset2():
    # this should produce FIVE results when unioned with the above; note the overlap with s1
    return SourceSet([s4, s5, s1])


@fixture
def sourcesetunion(sourceset1, sourceset2):
    # should have five sources.
    return SourceSet([sourceset1, sourceset2])


def test_sourcesetctors():
    ss = SourceSet(s1)
    assert len(ss.sourceSet) == 1
    assert s1 in ss.sourceSet

    ss = SourceSet([s1])
    assert len(ss.sourceSet) == 1
    assert s1 in ss.sourceSet

    ss = SourceSet([s1,s2])
    assert len(ss.sourceSet) == 2
    assert s1 in ss.sourceSet
    assert s2 in ss.sourceSet

    ss = SourceSet([s1,SourceSet(s2)])
    assert len(ss.sourceSet) == 2
    assert s1 in ss.sourceSet
    assert s2 in ss.sourceSet


def test_sourcesetunion(sourcesetunion):
    assert len(sourcesetunion.sourceSet) == 5
    assert s1 in sourcesetunion.sourceSet
    assert s2 in sourcesetunion.sourceSet
    assert s3 in sourcesetunion.sourceSet
    assert s4 in sourcesetunion.sourceSet
    assert s5 in sourcesetunion.sourceSet
