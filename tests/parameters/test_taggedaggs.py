"""
Tests for TaggedAggregates
"""
import pytest

from pcot.parameters.taggedaggregates import *


#
# Basic tests with no nested types
#

def test_taggeddict():
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", str, "foo", ["foo", "bar", "baz"]),
        c=("c", float, 3.14)
    )

    td = tdt.create()
    assert td['a'] == 10
    assert td['b'] == "foo"
    assert td['c'] == 3.14
    assert td.a == 10
    assert td.b == "foo"
    assert td.c == 3.14
    with pytest.raises(KeyError):
        print(td.d)

    assert len(td) == 3

    td['a'] = 20
    assert td['a'] == 20

    td.b = "bar"
    assert td.b == "bar"
    assert td['b'] == "bar"

    with pytest.raises(ValueError):
        td['a'] = "wibble"
    with pytest.raises(ValueError):
        td['a'] = 3.14
    with pytest.raises(ValueError):
        td['b'] = 64
    with pytest.raises(ValueError, match=r".*'wibble' is not in the list of valid strings foo,bar,baz"):
        td['b'] = 'wibble'  # not one of the valid strings

    with pytest.raises(KeyError):
        td['d'] = 12


def test_cant_set_with_plain_aggregate():
    tlt = TaggedListType(
        "a", int, [10, 20, 30], 0
    )
    tdt = TaggedDictType(
        b=("b", tlt),
    )

    td = tdt.create()
    with pytest.raises(ValueError):
        # we can't set what should be a TaggedList with a plain list,
        # even if it's the right type.
        td['b'] = [1,2,3]


def test_taggedlist():
    tlt = TaggedListType(
        "a", int, [10, 20, 30], 0
    )

    tl = tlt.create()
    assert tl[0] == 10
    assert len(tl) == 3

    tl[0] = 60
    assert tl[0] == 60

    with pytest.raises(ValueError):
        tl[0] = "wibble"
    with pytest.raises(ValueError):
        tl[0] = 3.14

    with pytest.raises(IndexError):
        tl[9] = 12

    # append an item
    tl.append(12)
    assert tl[3] == 12


def test_list_delete():
    tlt = TaggedListType(
        "a", int, [10, 20, 30], 0
    )

    tl = tlt.create()
    del tl[1]
    assert tl[0] == 10
    assert tl[1] == 30
    assert len(tl) == 2


#
# Now check that we can create nested types
#

def test_dict_of_lists():
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", TaggedListType("b", int, [10, 20, 30], 0), None),
        c=("c", float, 3.14)
    )

    td = tdt.create()
    assert td['a'] == 10
    assert td['b'][0] == 10
    assert td['b'][1] == 20
    assert td['b'][2] == 30
    assert td['c'] == 3.14
    assert len(td) == 3

    td['b'][0] = 60
    assert td['b'][0] == 60

    with pytest.raises(ValueError):
        td['b'][0] = "wibble"
    with pytest.raises(ValueError):
        td['b'][0] = 3.14

    with pytest.raises(IndexError):
        td['b'][9] = 12
    with pytest.raises(TypeError):  # the usual kind of error for this sort of nonsense.
        td['b']['frongworth'] = 12

    with pytest.raises(KeyError):
        td['d'] = 12


def test_dict_serialise():
    # create a simple TaggedDict of primitives
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", str, "foo"),
        c=("c", float, 3.14)
    )
    td = tdt.create()

    # check that we can serialise it into the expected structure
    serial = td.serialise()
    assert serial == {'c': 3.14, 'a': 10, 'b': 'foo'}


def test_list_serialise():
    ttt = TaggedListType(
        "a", int, [10, 20, 30], 0
    )
    tl = ttt.create()
    serial = tl.serialise()
    assert serial == [10, 20, 30]
    assert serial != [30, 20, 10]


def test_ser_complex():
    # a more complex structure made up of lists, dicts and tuples
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", TaggedListType("b", TaggedDictType(
            a=("a", int, 10),
            b=("b", str, "foo"),
            c=("c", float, 3.14)).setOrdered(), 2)),
        c=("c", float, 3.14),
        # a list of 4 identical dicts
        d=("d", TaggedListType("d", TaggedDictType(
            a=("a", int, 10),
            b=("b", str, "foo"),
            c=("c", float, 3.14)), 4)),
        # a list of 2 identical dicts, each with a tuple and a list inside
        e=("e", TaggedListType("e",
                               TaggedDictType(foo=("foo",
                                                   TaggedDictType(a=("a", int, 10),
                                                                   b=("ith", str, "blungle"),
                                                                   c=("c", float, 123.4)).setOrdered()
                                                   ),
                                              bar=("bar",
                                                   TaggedListType("none", int, [10, 20, 30], 0)
                                                   )
                                              )
                               , 2)
           )
    )

    td = tdt.create()

    # check that we can serialise it into the expected structure
    serial = td.serialise()
    assert serial == {'a': 10,
                      'b': [(10, 'foo', 3.14), (10, 'foo', 3.14)],
                      'c': 3.14,
                      'd': [
                          {'a': 10, 'b': 'foo', 'c': 3.14},
                          {'a': 10, 'b': 'foo', 'c': 3.14},
                          {'a': 10, 'b': 'foo', 'c': 3.14},
                          {'a': 10, 'b': 'foo', 'c': 3.14}
                      ],
                      'e': [
                          {'foo': (10, 'blungle', 123.4), 'bar': [10, 20, 30]},
                          {'foo': (10, 'blungle', 123.4), 'bar': [10, 20, 30]}
                      ]
                      }


def test_dict_ser_deser():
    tdt = TaggedDictType(
        a=("a", int, 1),
        b=("b", str, ""),
        c=("c", float, 0.0)
    )
    serial = {'c': 3.14, 'a': 10, 'b': 'foo'}

    td2 = tdt.deserialise(serial)
    assert td2._type == tdt
    assert td2['a'] == 10
    assert td2['b'] == "foo"
    assert td2['c'] == 3.14


def test_list_ser_deser():
    tlt = TaggedListType(
        "a", int, [0, 0, 0], 0
    )
    serial = [10, 20, 30]

    tl2 = tlt.deserialise(serial)
    assert tl2._type == tlt
    assert tl2[0] == 10
    assert tl2[1] == 20
    assert tl2[2] == 30


def test_list_iter():
    tlt = TaggedListType(
        "a", int, [0, 0, 0], 0
    )
    serial = [10, 20, 30]

    tl2 = tlt.deserialise(serial)
    for i, v in enumerate(tl2):
        assert v == serial[i]


def test_dict_of_ordered_dicts_ser_deser():
    tdt = TaggedDictType(
        a=("a", int, 0),
        b=("b", TaggedDictType(
            a=("a", int, 0),
            b=("b", str, ""),
            c=("c", float, 0.0)).setOrdered(), None),
        b1=("b1", TaggedDictType(
            aa=("aa", int, 0),
            bb=("bb", str, ""),
            cc=("c", str, "")).setOrdered(), None),
        c=("c", float, 0.0)
    )
    serial = {'c': 3.14, 'a': 10, 'b': (10, 'foo', 3.14), 'b1': (20, 'bar', 'dogfish')}

    td2 = tdt.deserialise(serial)
    assert td2._type == tdt
    assert td2['a'] == 10
    assert td2['b'][0] == 10
    assert td2['b'][1] == "foo"
    assert td2['b'][2] == 3.14
    assert td2['b1'][0] == 20
    assert td2['b1'][1] == "bar"
    assert td2['b1'][2] == "dogfish"
    assert td2['c'] == 3.14


def test_ordered_dict_destructuring():
    t = TaggedDictType(
        x=("x", int, 10),
        y=("y", int, 20)).setOrdered()

    td = t.create()
    x,y = td

    assert x == 10
    assert y == 20


def test_complex_ser_deser():
    # a more complex structure made up of lists, dicts and tuples
    tdt = TaggedDictType(
        a=("a", int, 0),
        b=("b", TaggedListType("b", TaggedDictType(
            a=("a", int, 0),
            b=("b", str, ""),
            c=("c", float, 0.0)).setOrdered(), 2)),
        c=("c", float, 0.0),
        # a list of 4 identical dicts
        d=("d", TaggedListType("d", TaggedDictType(
            a=("a", int, 0),
            b=("b", str, ""),
            c=("c", float, 0.0)), 4)),
        # a list of 2 identical dicts, each with a tuple and a list inside
        e=("e", TaggedListType("e",
                               TaggedDictType(foo=("foo",
                                                   TaggedDictType(a=("a", int, 0),
                                                                   b=("ith", str, ""),
                                                                   c=("c", float, 0.0)).setOrdered()),
                                              bar=("bar",
                                                   TaggedListType("none", int, [], 0)
                                                   )
                                              )
                               , 3)
           )
    )
    serial = {'a': 10,
              'b': [(10, 'foo', 3.14), (10, 'foo', 3.14)],
              'c': 3.14,
              'd': [
                  {'a': 12, 'b': 'foo', 'c': 3.11},
                  {'a': 14, 'b': 'foo', 'c': 3.15},
                  {'a': 16, 'b': 'foo', 'c': 3.14}
              ],
              'e': [
                  {'foo': (10, 'blungle', 123.67), 'bar': [10, 20, 30]},
                  {'foo': (10, 'blungle', 120.4), 'bar': [10, 20, 30]}
              ]
              }

    # deserialise from that structure
    td2 = tdt.deserialise(serial)
    assert td2._type == tdt

    # serialise it again
    serial2 = td2.serialise()
    # check it's the same!
    assert serial2 == serial


def test_setbydot():
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", str, "foo"),
        c=("c", float, 3.14)
    )

    td = tdt.create()

    td.a = 20
    assert td['a'] == 20
    with pytest.raises(KeyError):
        assert td[0] == 20

    ttt = TaggedDictType(
        a=("a", int, 10),
        b=("b", str, "foo"),
        c=("c", float, 3.14)
    ).setOrdered()

    tt = ttt.create()

    tt.a = 20
    assert tt['a'] == 20
    assert tt.a == 20
    assert tt[0] == 20


def test_typing():
    # checking that bad types throw errors
    with pytest.raises(ValueError):
        tdt = TaggedDictType(
            a=("a", int, "cat")
        )

    with pytest.raises(ValueError):
        tdt = TaggedDictType(
            a=("a", str, 7)
        )

    with pytest.raises(ValueError):
        tdt = TaggedDictType(
            a=("a", TaggedDictType(
                b=("b", str, "foo"),
            ), 7)
        )

    with pytest.raises(ValueError):
        tdt = TaggedDictType(
            a=("a", TaggedDictType(
                b=("b", str, 7),
            ))
        )

    with pytest.raises(ValueError):
        TaggedListType(
            "a", int, [10, 20, "cat"], 0
        )

    TaggedListType(
        "a", int, [10, 20, 30], 0
    )

    with pytest.raises(ValueError):
        TaggedListType(
            "a", int, [10, 20, 30], "cat"
        )

    # now test the optional type - this is fine
    TaggedDictType(
        a=("a", int, 10),
        b=("b", Maybe(str), "foo"),
        c=("c", float, 3.14)
    )

    # and this
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", Maybe(str), None),
        c=("c", float, 3.14)
    )

    # not this though!
    with pytest.raises(ValueError):
        TaggedDictType(
            a=("a", int, 10),
            b=("b", Maybe(str), 3.14),
            c=("c", float, 3.14)
        )

    # let's create an example of that TD with a None value for b
    td = tdt.create()
    assert td.a == 10
    assert td.b is None
    assert td.c == 3.14

    # let's set it to a string
    td.b = "hello"
    assert td.b == "hello"
    # and set it back to null
    td.b = None
    assert td.b is None
    # and now set it to something it can't be
    with pytest.raises(ValueError):
        td.b = 4


def test_optional_aggregates():
    tlt = TaggedListType(
        "a", Maybe(int), [10, 20, 30], 0
    )

    tdt = TaggedDictType(
        a=("a", tlt),
        b=("b", Maybe(tlt), None),
        c=("c", float, 3.14)
    )

    td = tdt.create()
    assert td['a'].get() == [10, 20, 30]
    assert td['b'] is None
    assert td['c'] == 3.14

    td['b'] = TaggedList(tlt, [10, 204, 30])

    assert td.b.get() == [10, 204, 30]


def test_optional_ser():
    tlt = TaggedListType(
        "a", Maybe(int), [10, 20, 30], 0
    )

    tdt = TaggedDictType(
        a=("a", tlt),
        b=("b", Maybe(tlt), None),
        c=("c", Maybe(float), 3.14)
    )

    td = tdt.create()

    s = td.serialise()
    assert s == {'a': [10, 20, 30], 'b': None, 'c': 3.14}

    td = tdt.deserialise(s)
    s = td.serialise()
    assert s == {'a': [10, 20, 30], 'b': None, 'c': 3.14}


def test_tagged_variant_dict():
    tdt1 = TaggedDictType(
        a=("a", int, 10),
        b=("b", str, "foo"),
        c=("c", float, 3.14)
    )
    tdt2 = TaggedDictType(
        a=("a", int, 10),
        b=("b", float, 3.14),
        d=("d", str, "wibble"),
        e=("e", bool, False)
    )

    tvdt = TaggedVariantDictType("type",
                                 {
                                        "type1": tdt1,
                                        "type2": tdt2
                                    })

    # type for a list of variant dicts, where the underlying dicts are either type1 or type2.
    tl = TaggedListType("stuff", tvdt, 0)
    # create the list
    ll = tl.create()

    # create an item - we do this by creating the underlying dict, then creating a TaggedVariantDict
    d = tdt1.create()
    d.a = 212       # set an item in it while we're here
    # now create a TaggedVariantDict and set it to contain that item
    t = tvdt.create().set(d)
    # and add it to the list.
    ll.append(t)

    d = tdt2.create()
    d.a = 2121
    t = tvdt.create().set(d)
    ll.append(t)

    s = ll.serialise()
    ll = tl.deserialise(s)

    assert len(ll) == 2
    assert ll[0].get_type() == 'type1'
    assert ll[0].get().a == 212
    assert ll[0].get().type == tdt1

    assert ll[1].get_type() == 'type2'
    assert ll[1].get().e is False
    assert ll[1].get().type == tdt2


def test_python_dict():
    """is it possible to have a TaggedDict containing a basic python dict?"""
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", dict, {"foo": 1, "bar": 2}),
        c=("c", float, 3.14)
    )

    td = tdt.create()
    assert td['a'] == 10
    assert td['b']['foo'] == 1
    assert td['b']['bar'] == 2
    assert td['c'] == 3.14

    td['b']['foo'] = 3

    # make sure modifying the dict hasn't modified the default (i.e. that a copy was made)
    td2 = tdt.create()
    assert td2['b']['foo'] == 1

    # does it serialise?

    s = td.serialise()
    assert s == {'a': 10, 'b': {'foo': 3, 'bar': 2}, 'c': 3.14}


def test_valid_strings():
    """Test that only valid strings options are accepted in a TaggedDict which specified them for a string element"""
    tdt = TaggedDictType(
        a=("a", str, "foo", ["foo", "bar", "baz"]),
        b=("b", str, "foo")
    )

    td = tdt.create()

    td['a'] = "bar"
    assert td['a'] == "bar"

    with pytest.raises(ValueError, match=r".*'wibble' is not in the list of valid strings foo,bar,baz"):
        td['a'] = 'wibble'  # not one of the valid strings

    for xx in ["foo", "bar", "baz"]:
        td['a'] = xx  #  this are all OK because they are in the list of valid strings

    td['b'] = 'wibble'  # not one of the valid strings, but this is OK because it's not specified with a valid list
