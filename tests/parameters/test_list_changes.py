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
    bar=("bar", basetdt, None), # just a dict
    lst=("list", TaggedListType("list of dicts", basetdt, 0), None),   # list with no items
    lst2=("list of int", TaggedListType("list of ints", int, [], 23), None)   # list with no items
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


def test_add_multiple_items_doubledot():
    """Using the horrible doubledot method to add to items"""
    td = tdt.create()
    f = ParameterFile().parse("""
    foo.lst2+ = 23
    ..lst2+ = 24
    foo.lst2+ = 25
    foo.lst2+ = 26
    ..lst2+ = 27
    """)

    f.apply({"foo": td})

    assert [x for x in td.lst2] == [23, 24, 25, 26, 27]


def test_add_multiple_items_shorthand1():
    """Using the singledot method to add to items"""
    td = tdt.create()
    f = ParameterFile().parse("""
    foo.lst2+ = 23
    .+ = 24
    .+ = 200
    foo.lst2+ = 25
    foo.lst2+ = 26
    .+ = 27
    """)

    f.apply({"foo": td})

    assert [x for x in td.lst2] == [23, 24, 200, 25, 26, 27]


def test_add_multiple_items_shorthand2():
    """Using the singledot method to add to items - this time TD"""
    td = tdt.create()
    f = ParameterFile().parse("""
    foo.lst+.a = flibble
    .b = 100
    foo.lst2+ = 25
    foo.lst2+ = 26
    .+ = 27
    foo.lst+.a = bvoz
    .b = 101
    """)

    f.apply({"foo": td})

    assert [x for x in td.lst2] == [25, 26, 27]
    assert td.lst[0].a == "flibble"
    assert td.lst[0].b == 100
    assert td.lst[1].a == "bvoz"
    assert td.lst[1].b == 101

