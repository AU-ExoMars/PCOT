import pytest

from pcot.parameters.parameterfile import ParameterFile
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType

basetdt = TaggedDictType(
    a=("a", str, "foo"),
    b=("b", int, 10)
)

# the base structure we'll use is a dict, containing a single element - a list of initially zero dicts
# like the one above.

tdt = TaggedDictType(
    lst=("list", TaggedListType("list of dicts", basetdt, 0), None)   # list with no items
)


def test_no_items():
    td = tdt.create()
    f = ParameterFile().parse("foo.lst[0].a = bar")
    with pytest.raises(IndexError):
        f.apply({"foo": td})


def test_add_item():
    """Add an item to the list without changing any values"""
    td = tdt.create()
    f = ParameterFile().parse("foo.lst+")
    f.apply({"foo": td})

    assert len(td.lst) == 1
