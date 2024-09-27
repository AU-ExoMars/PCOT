import pytest

from pcot.parameters.parameterfile import ParameterFile
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType, TaggedVariantDictType, \
    Maybe

base_tagged_dict_type = TaggedDictType(
    a=("a desc", int, 10),
    b=("b desc", str, "foo"),
    c=("c desc", float, 3.14)
)

base_tagged_list_type = TaggedListType(
    "base list", int, [10, 20, 30], -1
)

base_tagged_ordered_dict_type = TaggedDictType(
    d=("dee", float, 3.24),
    e=("eee", int, 11),
    f=("eff", str, "dog")
).setOrdered()


list_of_ordered_dicts_type = TaggedListType("list of ODs", base_tagged_ordered_dict_type, 0)


tagged_dict_type = TaggedDictType(
    base=("a base tagged dict", base_tagged_dict_type, None),
    bloon=("a bloon", str, "bloon"),
    base2=("another base tagged dict", base_tagged_dict_type, None),
    list1=("a list", base_tagged_list_type),  # empty list of ints
    list2=("a list of ordered dicts", list_of_ordered_dicts_type, None)
)

tagged_variant_dict_type = TaggedVariantDictType("type",
                                                 {
                                                     "x": TaggedDictType(
                                                         type=("type", str, "x"),
                                                         a=("a desc", int, 10),
                                                         b=("b desc", str, "foo"),
                                                         c=("c desc", float, 3.14)
                                                     ),
                                                     "y": TaggedDictType(
                                                         type=("type", str, "y"),
                                                         d=("dee", float, 3.24),
                                                         e=("eee", int, 11),
                                                         f=("eff", str, "dog"))}
                                                 )

tagged_variant_dict_in_dict_type = TaggedDictType(
    base=("an ordinary tagged dict", base_tagged_dict_type, None),
    bloon=("a bloon", str, "bloon"),
    lst=("a list of variant dicts",
         TaggedListType("list of variant dicts", tagged_variant_dict_type, 0), None)
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
    f.apply({"zog": td})
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

    # wrong kind of index!
    f = ParameterFile().parse("foo[bar] = 22")
    with pytest.raises(TypeError):
        f.apply({"foo": tl})


def test_list_add_non_ta():
    """Test adding an item to a list of non-tagged aggregates"""
    td = tagged_dict_type.create()
    f = ParameterFile().parse("foo.list1+ = 20")
    f.apply({"foo": td})
    assert len(td.list1) == 4
    assert td.list1[3] == 20
    f = ParameterFile().parse("foo.list1+")     # add default item
    f.apply({"foo": td})
    assert len(td.list1) == 5
    assert td.list1[4] == -1


def test_list_add_non_ta_nodefault():
    """You have to provide a default append item for non-TA lists if you ever want to append to them"""
    with pytest.raises(ValueError) as info:
        tlt = TaggedListType("base list", int, [10])     # no default append
    assert "Default append not provided" in str(info.value)


def test_list_add_ta():
    """Test adding an item to a list of tagged aggregates"""
    td = tagged_dict_type.create()
    f = ParameterFile().parse("foo.list2+")
    f.apply({"foo": td})
    assert len(td.list2) == 1
    assert td.list2[0].d == 3.24
    assert td.list2[0].e == 11
    assert td.list2[0].f == "dog"


def test_list_add_ta_cursor():
    """Check that when we add to a list of TAs, the cursor is left in the right place,
    which is actually down a level from where we might think it should be!"""
    td = tagged_dict_type.create()
    f = ParameterFile().parse("""
        foo.list2+.d = 36
        # we are at foo.list2.-1 because we added to the list and the cursor
        # was set to the last item in the list.
        # . will keep us at foo.list2.-1 (i.e. sibling, so ".d" would edit a field in the last item)
        # .. will take us to foo.list2 (up one level)
        # ... will take us to foo (up two levels) which is where we want to be
        ...list2+.d = 48
    """)
    f.dump()
    f.apply({"foo": td})
    assert len(td.list2) == 2
    assert td.list2[0].d == 36
    assert td.list2[1].d == 48


def test_dict_in_dict():
    td = tagged_dict_type.create()
    f = ParameterFile().parse("foo.base.a = 22")
    f.apply({"foo": td})
    assert td.base.a == 22

    td = tagged_dict_type.create()
    f = ParameterFile().parse("foo.base.a=12\n.b = bar\n.c = 43.5\n")
    f.apply({"foo": td})
    assert td.base.a == 12
    assert td.base.b == "bar"
    assert td.base.c == 43.5

    td = tagged_dict_type.create()
    f = ParameterFile().parse("""
    foo.base.a=12
    .b = bar
    ..base2.b = foo
    .c=48
    """)
    f.apply({"foo": td})
    assert td.base.a == 12
    assert td.base.b == "bar"
    assert td.base2.b == "foo"
    assert td.base2.c == 48  # ..base2.b will have switched the path to base2
    assert td.base.c == 3.14  # should be unchanged


def test_maybe_in_dict():
    tdt = TaggedDictType(
        a=("a", str, "foo"),
        b=("b", Maybe(str), None),
        c=("c", Maybe(int), 10)
    )
    td = tdt.create()
    assert(td.b is None)
    assert(td.c == 10)

    f = ParameterFile().parse("foo.b = bar")
    f.apply({"foo": td})
    assert td.b == "bar"

    f = ParameterFile().parse("foo.c = bar")
    with pytest.raises(ValueError):
        f.apply({"foo": td})
    assert td.c == 10

    f = ParameterFile().parse("foo.c = 22")
    f.apply({"foo": td})
    assert td.c == 22





def test_add_to_variant_dict_list():
    td = tagged_variant_dict_in_dict_type.create()
    # check the initial state
    assert len(td.lst) == 0

    # there isn't an "invalid" variant dict type in the variant dict, so this will fail.
    with pytest.raises(ValueError) as info:
        f = ParameterFile().parse("foo.lst+invalid")
        f.apply({"foo": td})
    assert "not a valid variant" in str(info)

    # now add a valid variant
    f = ParameterFile().parse("foo.lst+x")
    f.apply({"foo": td})
    assert len(td.lst) == 1
    # check that the variant dict has been created
    assert td.lst[0].get_type() == "x"      # can do this
    assert td.lst[0].get()["type"] == "x"   # or this
    assert td.lst[0].type != "x" # but NOT THIS - this gets the dict type

    # now add another valid variant
    f = ParameterFile().parse("foo.lst+y")
    f.apply({"foo": td})
    assert len(td.lst) == 2
    assert td.lst[1].get_type() == "y"

    # look at members - you have to use get() to get the dict
    # from the variant
    assert td.lst[1].get().d == 3.24
    assert td.lst[0].get().b == "foo"


def test_modify_variant_dict_list():
    td = tagged_variant_dict_in_dict_type.create()
    f = ParameterFile().parse("foo.lst+x")
    f.apply({"foo": td})
    assert len(td.lst) == 1
    # check that the variant dict has been created
    assert td.lst[0].get_type() == "x"
    assert td.lst[0].get().b == "foo"   # check a value

    # modify
    f = ParameterFile().parse("foo.lst[0].b = bar")
    f.apply({"foo": td})


def test_maybe_list_in_dict():
    """Test we can add to a Maybe(list) in a dict"""
    tlt = TaggedListType("list", int, [], 0)
    tdt = TaggedDictType(
        base=("an ordinary tagged dict", base_tagged_dict_type, None),
        bloon=("a bloon", str, "bloon"),
        lst=("a list", Maybe(tlt), None)
        )

    # should fail; the list is null
    td = tdt.create()
    f = ParameterFile().parse("foo.lst+ = 22")
    with pytest.raises(ValueError) as info:
        f.apply({"foo": td})
    assert "Cannot add to a null list" in str(info.value)

    td = tdt.create()
    td.lst = tlt.create()
    f = ParameterFile().parse("foo.lst+ = 22")
    f.apply({"foo": td})

@pytest.mark.xfail(raises=NotImplementedError)
def test_modify_variant_dict_in_dict2():
    """In this code we aren't adding a variant dict to a list but
    creating one in a normal dict.
    """
    tdt = TaggedDictType(
        base=("an ordinary tagged dict", base_tagged_dict_type, None),
        bloon=("a bloon", str, "bloon"),
        dd=("a variant dict", tagged_variant_dict_type, None)
        )

    td = tdt.create()

    # tell it to create an X dict in the dd variant dict
    f = ParameterFile().parse("foo.dd/x.a = 22")
    raise NotImplementedError()
