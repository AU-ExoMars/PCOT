import pytest

from pcot.parameters.parameterfile import ParameterFile, ApplyException
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType, TaggedVariantDictType, \
    Maybe, taggedPointListType, taggedPointType

base_tagged_dict_type = TaggedDictType(
    a=("a desc", int, 10),
    b=("b desc", str, "foo"),
    c=("c desc", float, 3.14),
)

base_tagged_list_type = TaggedListType(
    "base list", int, [10, 20, 30], -1
)

base_tagged_ordered_dict_type = TaggedDictType(
    d=("dee", float, 3.24),
    e=("eee", int, 11),
    f=("eff", str, "dog"),
    g=("d desc", TaggedListType("embedded list", int, [1, 2, 3, 4, 5, 6], 48))
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
                                                         c=("c desc", float, 3.14),
                                                     ),
                                                     "y": TaggedDictType(
                                                         type=("type", str, "y"),
                                                         d=("dee", float, 3.24),
                                                         e=("eee", int, 11),
                                                         f=("eff", str, "dog"),
                                                         g=("gee", TaggedDictType(
                                                                h=("h", int, 1),
                                                                i=("i", int, 2)), None)
                                                     )
                                                 }
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
    """Make sure that a parameter file with irrelevant changes throws an error"""
    td = tagged_dict_type.create()
    s = td.serialise()

    f = ParameterFile().parse("""
    foo.bar.baz = 10
    """)
    with pytest.raises(ApplyException):
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
    with pytest.raises(ApplyException) as e:
        f.apply({"foo": td})
    assert "expected int" in str(e)

    # check that invalid keys raise an error
    f = ParameterFile().parse("foo.d = 11")
    with pytest.raises(ApplyException):
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
    with pytest.raises(ApplyException):
        f.apply({"foo": td})


def test_base_list():
    tl = base_tagged_list_type.create()
    f = ParameterFile().parse("foo[1] = 22")
    f.apply({"foo": tl})
    assert tl[1] == 22

    # wrong kind of index!
    f = ParameterFile().parse("foo[bar] = 22")
    with pytest.raises(ApplyException):
        f.apply({"foo": tl})


def test_list_add_non_ta():
    """Test adding an item to a list of non-tagged aggregates"""
    td = tagged_dict_type.create()
    f = ParameterFile().parse("foo.list1.+ = 20")
    f.apply({"foo": td})
    assert len(td.list1) == 4
    assert td.list1[3] == 20
    f = ParameterFile().parse("foo.list1.+")  # add default item
    f.apply({"foo": td})
    assert len(td.list1) == 5
    assert td.list1[4] == -1


def test_list_add_non_ta_nodefault():
    """You have to provide a default append item for non-TA lists if you ever want to append to them"""
    with pytest.raises(ValueError) as info:
        tlt = TaggedListType("base list", int, [10])  # no default append
    assert "Default append not provided" in str(info.value)


def test_list_add_ta():
    """Test adding an item to a list of tagged aggregates"""
    td = tagged_dict_type.create()
    f = ParameterFile().parse("foo.list2.+")
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
        foo.list2.+.d = 36
        ...list2.+.d = 48
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
    assert (td.b is None)
    assert (td.c == 10)

    f = ParameterFile().parse("foo.b = bar")
    f.apply({"foo": td})
    assert td.b == "bar"

    f = ParameterFile().parse("foo.c = bar")
    with pytest.raises(ApplyException):
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
    with pytest.raises(ApplyException) as info:
        f = ParameterFile().parse("foo.lst.+invalid")
        f.apply({"foo": td})
    assert "not a valid variant" in str(info)

    # now add a valid variant
    f = ParameterFile().parse("foo.lst.+x")
    f.apply({"foo": td})
    assert len(td.lst) == 1
    # check that the variant dict has been created
    assert td.lst[0].get_type() == "x"  # can do this
    assert td.lst[0].get()["type"] == "x"  # or this
    assert td.lst[0].type != "x"  # but NOT THIS - this gets the dict type

    # now add another valid variant
    f = ParameterFile().parse("foo.lst.+y")
    f.apply({"foo": td})
    assert len(td.lst) == 2
    assert td.lst[1].get_type() == "y"

    # look at members - you have to use get() to get the dict
    # from the variant
    assert td.lst[1].get().d == 3.24
    assert td.lst[0].get().b == "foo"


def test_modify_variant_dict_list():
    td = tagged_variant_dict_in_dict_type.create()
    f = ParameterFile().parse("foo.lst.+x")
    f.apply({"foo": td})
    assert len(td.lst) == 1
    # check that the variant dict has been created
    assert td.lst[0].get_type() == "x"
    assert td.lst[0].get().b == "foo"  # check a value

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
    f = ParameterFile().parse("foo.lst.+ = 22")
    with pytest.raises(ApplyException) as info:
        f.apply({"foo": td})
    assert "Cannot add to a null list" in str(info.value)

    td = tdt.create()
    td.lst = tlt.create()
    f = ParameterFile().parse("foo.lst.+ = 22")
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


def test_change_top_level_list():
    """Create a list at the top level and try modifying it"""

    tl = list_of_ordered_dicts_type.create()

    # first an add - this should create a new default item
    f = ParameterFile().parse("foo.+")
    f.apply({"foo": tl})

    assert len(tl) == 1
    assert tl[0].d == 3.24

    # here we create a fresh list, then add an item and modifythat item in a single step.
    tl = list_of_ordered_dicts_type.create()
    f = ParameterFile().parse("foo.+.d = 12")
    f.apply({"foo": tl})

    assert len(tl) == 1
    assert tl[0].d == 12

    #on another fresh list:
    #  create a new item at the top level
    #  add a new item to that item's sublist
    tl = list_of_ordered_dicts_type.create()
    f = ParameterFile().parse("foo.+.g.+")
    f.apply({"foo": tl})
    assert len(tl) == 1  # foo is a list containing one item, a dict
    assert len(tl[0]) == 4  # four items in the dict, in which g is a list
    assert len(tl[0].g) == 7  # six items in the list
    assert tl[0].g[6] == 48  # the last item is 48 (default new item)

    # as above, and  add a value to the last item
    tl = list_of_ordered_dicts_type.create()
    f = ParameterFile().parse("foo.+.g.+ = 101")
    f.apply({"foo": tl})
    assert len(tl) == 1  # foo is a list containing one item, a dict
    assert len(tl[0]) == 4  # four items in the dict, in which g is a list
    assert len(tl[0].g) == 7  # seven items in the list
    assert tl[0].g[6] == 101  # the last item is 101

    # now we are going to break down the changes
    tl = list_of_ordered_dicts_type.create()
    f = ParameterFile().parse("""
    foo.+               # add an item
    .g.+ = 101          # in that item, add an item to g and set it to 101
    """)
    f.apply({"foo": tl})
    assert len(tl) == 1  # foo is a list containing one item, a dict
    assert len(tl[0]) == 4  # four items in the dict, in which g is a list
    assert len(tl[0].g) == 7  # seven items in the list
    assert tl[0].g[6] == 101  # the last item is 101

    tl = list_of_ordered_dicts_type.create()
    f = ParameterFile().parse("""
    foo.+
    .g.+ = 101
    ...+.g.+ = 102
    ...+.g.+ = 103
    foo.+.g.+ = 104
    """)

    f.apply({"foo": tl})
    assert len(tl) == 4
    assert len(tl[1]) == 4
    assert len(tl[1].g) == 7
    assert tl[1].g[6] == 102
    assert tl[2].g[6] == 103
    assert tl[3].g[6] == 104


def test_reset_embedded_plain_value():
    td = tagged_dict_type.create()
    # change some items so they aren't the same as the defaults
    td.base.a = 1032
    td.base.b = "bar"
    td.bloon = "xyz"
    # save the state
    td.generate_original()

    # now change them again
    td.base.a = 1033
    td.base.b = "baz"
    td.bloon = "abc"

    # reset base.a in a parameter file
    f = ParameterFile().parse("reset foo.base.a")
    f.apply({"foo": td})

    # check that base.a has been reset
    assert td.base.a == 1032
    # and the others haven't
    assert td.base.b == "baz"
    assert td.bloon == "abc"


def test_reset_dict_embedded_in_top_level():
    td = tagged_dict_type.create()
    # change some items so they aren't the same as the defaults
    td.base.a = 1032
    td.base.b = "bar"
    td.base.c = 2.1
    td.bloon = "xyz"
    # save the state
    td.generate_original()

    # now change them again
    td.base.a = 1033
    td.base.b = "baz"
    td.base.c = 2.2
    td.bloon = "abc"

    # reset base in a parameter file
    f = ParameterFile().parse("reset foo.base")
    f.apply({"foo": td})

    # check that base has been reset
    assert td.base.a == 1032
    assert td.base.b == "bar"
    assert td.base.c == 2.1
    assert td.bloon == "abc"  # unchanged


def test_reset_dict_in_list():
    td = tagged_dict_type.create()
    # change some items so they aren't the same as the defaults
    td.base.a = 1032
    td.base.b = "bar"
    td.base.c = 2.1
    td.bloon = "xyz"
    # add to the list2 and change a couple of members - easiest to use a parameter file
    f = ParameterFile().parse("foo.list2.+.d = 36.1\n.f=blart48")
    f.apply({"foo": td})
    # save the state
    td.generate_original()

    # check the values
    assert len(td.list2) == 1
    assert td.list2[0].d == 36.1
    assert td.list2[0].f == "blart48"

    # now change them again
    td.list2[0].d = 36.2
    td.list2[0].f = "blart49"
    # confirm the changes
    assert td.list2[0].d == 36.2
    assert td.list2[0].f == "blart49"
    # reset
    f = ParameterFile().parse("reset foo.list2[0]")
    f.apply({"foo": td})
    # check that the values have been reset
    assert td.list2[0].d == 36.1
    assert td.list2[0].f == "blart48"

    # change them back again
    td.list2[0].d = 36.2
    td.list2[0].f = "blart49"
    # confirm the changes
    assert td.list2[0].d == 36.2
    assert td.list2[0].f == "blart49"

    # now just reset one of those items.
    f = ParameterFile().parse("reset foo.list2[0].d")
    f.apply({"foo": td})
    # check that only that value has been reset
    assert td.list2[0].d == 36.1
    assert td.list2[0].f == "blart49"

    # repeat that test with the alternate list index format
    td.list2[0].d = 36.2
    td.list2[0].f = "blart49"
    f = ParameterFile().parse("reset foo.list2.0.d")
    f.apply({"foo": td})
    assert td.list2[0].d == 36.1
    assert td.list2[0].f == "blart49"


def test_reset_variant_dict():
    td = tagged_variant_dict_in_dict_type.create()
    # add an item to the list of variant dicts
    v = tagged_variant_dict_type.create("x")
    td.lst.append(v)
    td.lst[0].get().a = 100  # remember, get() deferences the variable dict
    td.lst[0].get().b = "bar"

    # save that state
    td.generate_original()

    # make some changes
    td.lst[0].get().a = 101
    td.lst[0].get().b = "baz"

    # now reset the entire dict
    f = ParameterFile().parse("reset foo.lst[0]")
    f.apply({"foo": td})
    # check things match the saved state
    assert len(td.lst) == 1
    assert td.lst[0].get().a == 100
    assert td.lst[0].get().b == "bar"


def test_reset_value_in_variant_dict():
    td = tagged_variant_dict_in_dict_type.create()
    # add an item to the list of variant dicts
    v = tagged_variant_dict_type.create("x")
    td.lst.append(v)
    td.lst[0].get().a = 100  # remember, get() deferences the variable dict
    td.lst[0].get().b = "bar"

    # save that state
    td.generate_original()

    # make some changes
    td.lst[0].get().a = 101
    td.lst[0].get().b = "baz"

    # now reset the entire dict
    f = ParameterFile().parse("reset foo.lst[0].a")
    f.apply({"foo": td})
    # check unchanged values match saved state
    assert len(td.lst) == 1
    assert td.lst[0].get().a == 100
    assert td.lst[0].get().b == "baz"  # should be unchanged


def test_reset_dict_in_variant_dict():
    td = tagged_variant_dict_in_dict_type.create()
    # add an item to the list of variant dicts
    v = tagged_variant_dict_type.create("y")
    td.lst.append(v)
    # change stuff in the dict inside the variant dict and elsewhere
    td.bloon = "trampoline"
    td.lst[0].get().d = 10.1
    td.lst[0].get().e = 20
    td.lst[0].get().f = "cat"
    # g is a dict, and is itself a member of the dict inside the variant dict
    td.lst[0].get().g.h = 100
    td.lst[0].get().g.i = 200

    # save that state
    td.generate_original()

    # now make some changes
    td.bloon = "kelp"
    td.lst[0].get().d = 10.5
    td.lst[0].get().e = 21
    td.lst[0].get().f = "cat or meringue"
    # g is a dict, and is itself a member of the dict inside the variant dict
    td.lst[0].get().g.h = 101
    td.lst[0].get().g.i = 202

    # reset the dict inside the variant
    f = ParameterFile().parse("reset foo.lst[0].g")
    f.apply({"foo": td})

    # check data is as it was just modified, except in the dict
    # inside the variant
    assert td.bloon == "kelp"
    assert td.lst[0].get().d == 10.5
    assert td.lst[0].get().e == 21
    assert td.lst[0].get().f == "cat or meringue"
    # these will be changed back
    assert td.lst[0].get().g.h == 100
    assert td.lst[0].get().g.i == 200


pointInDictType = TaggedDictType(
    p=("point", taggedPointType, None)
)

def test_list_shorthand_in_ordered_dict():
    """Check the notation a.b.c = [1,2,3] where the thing we are setting is an ordered dict"""

    d = pointInDictType.create()

    f = ParameterFile().parse("foo.p = [10,20]")
    f.apply({"foo": d})

    assert d.p.x == 10
    assert d.p.y == 20


# leaving this for now for backcompat.
@pytest.mark.xfail
def test_list_shorthand_in_ordered_dict_too_long():
    d = pointInDictType.create()
    f = ParameterFile().parse("foo.p = [1,2,3]")
    with pytest.raises(ApplyException) as e:
       f.apply({"foo": d})
    assert "Too many" in str(e.value)


def test_list_shorthand_in_ordered_dict_bad_format():

    d = pointInDictType.create()
    f = ParameterFile().parse("foo.p = 1,2,3")
    with pytest.raises(ApplyException) as e:
       f.apply({"foo": d})
    assert "Invalid format for data" in str(e.value)
