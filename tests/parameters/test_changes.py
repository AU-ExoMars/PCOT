import pytest

from pcot.parameters.parameterfile import ParameterFile
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType, TaggedTupleType

base_tagged_dict_type = TaggedDictType(
    a=("a desc", int, 10),
    b=("b desc", str, "foo"),
    c=("c desc", float, 3.14)
)

base_tagged_list_type = TaggedListType(
    "base list", int, [10, 20, 30]
)

base_tagged_tuple_type = TaggedTupleType(
    d=("dee", float, 3.24),
    e=("eee", int, 11),
    f=("eff", str, "dog")
)

tagged_dict_type = TaggedDictType(
    base=("a base tagged dict", base_tagged_dict_type, None),
    bloon=("a bloon", str, "bloon"),
    base2=("another base tagged dict", base_tagged_dict_type, None),
    list1=("a list", base_tagged_list_type),     # empty list
    tuple1=("a tuple", base_tagged_tuple_type)    # empty tuple
)


def test_changes_none():
    """Make sure that a blank parameter file doesn't do anything"""
    td = tagged_dict_type.create()
    s = td.serialise()

    f = ParameterFile().parse("")
    f.apply(td)
    assert td.serialise() == s


def test_changes_irrelevant():
    """Make sure that a parameter file with irrelevant changes doesn't do anything"""
    td = tagged_dict_type.create()
    s = td.serialise()

    f = ParameterFile().parse("""
    foo.bar.baz = 10
    """)
    f.apply({"zog":td})
    assert td.serialise() == s


def test_changes_base_dict():
    td = base_tagged_dict_type.create()
    # feed in a very simple parameter file
    f = ParameterFile().parse("foo.a = 11")
    # apply that parameter file to the tagged dict, which we give the name "foo"
    f.apply({"foo": td})
    # and check that "a" in foo has changed.
    assert td.a == 11
    # now check that the other values haven't changed
    assert td.b == "foo"
    assert td.c == 3.14

    # check that invalid values raise an error
    f = ParameterFile().parse("foo.a = bar")
    with pytest.raises(ValueError):
        f.apply({"foo": td})

    # check that invalid keys raise an error
    f = ParameterFile().parse("foo.d = 11")
    with pytest.raises(KeyError):
        f.apply({"foo": td})


def test_changes_base_dict_multiple():
    td = base_tagged_dict_type.create()
    # feed in a very simple parameter file
    f = ParameterFile().parse("foo.b = bar\n.a = 11\n.c = 32")
    # apply that parameter file to the tagged dict, which we give the name "foo"
    f.apply({"foo": td})
    # and check that "a" in foo has changed.
    assert td.a == 11
    assert td.b == "bar"
    assert td.c == 32


def test_changes_bad_type():
    td = base_tagged_dict_type.create()
    f = ParameterFile().parse("foo.b = bar\n.a = bar")
    with pytest.raises(ValueError):
        f.apply({"foo": td})


def test_base_list():
    tl = base_tagged_list_type.create()
    f = ParameterFile().parse("foo[1] = 22")
    f.apply({"foo": tl})
    assert tl[1] == 22

    f = ParameterFile().parse("foo[bar] = 22")
    with pytest.raises(ValueError):
        f.apply({"foo": tl})


def test_base_tuple():
    tt = base_tagged_tuple_type.create()
    f = ParameterFile().parse("foo.d = 22")
    f.apply({"foo": tt})
    assert tt.d == 22
    assert isinstance(tt.d, float)

    f = ParameterFile().parse("foo[e] = 44")
    f.apply({"foo": tt})
    assert tt.e == 44
    assert isinstance(tt.e, int)

    f = ParameterFile().parse("foo[f] = bar")
    f.apply({"foo": tt})
    assert tt.f == "bar"

    f = ParameterFile().parse("foo[g] = 22")
    with pytest.raises(KeyError):
        f.apply({"foo": tt})


def test_dict_in_dict():
    td = tagged_dict_type.create()
    f = ParameterFile().parse("foo.base.a = 22")
    f.apply({"foo": td})
    assert td.base.a == 22

    f = ParameterFile().parse("foo.base.a=12\n.b = bar\n.c = 43.5\n")
    f.apply({"foo": td})
    assert td.base.a == 12
    assert td.base.b == "bar"
    assert td.base.c == 43.5

    f = ParameterFile().parse("foo.base.a=12\n.b = bar\n..base2.b = foo\n.c=48\n")
    f.apply({"foo": td})
    assert td.base.a == 12
    assert td.base.b == "bar"
    assert td.base2.b == "foo"
    assert td.base2.c == 48     # ..base2.b will have switched the path to base2
    assert td.base.c == 3.14    # should be unchanged

