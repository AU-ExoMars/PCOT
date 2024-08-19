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
    base2=("another base tagged dict", base_tagged_dict_type, None)
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


def test_changes_base_dict_multiple():
    td = base_tagged_dict_type.create()
    # feed in a very simple parameter file
    f = ParameterFile().parse("foo.a = 11\n.b = bar\n.c = 32")
    # apply that parameter file to the tagged dict, which we give the name "foo"
    f.apply({"foo": td})
    # and check that "a" in foo has changed.
    assert td.a == 11
    assert td.b == "bar"
    assert td.c == 32
