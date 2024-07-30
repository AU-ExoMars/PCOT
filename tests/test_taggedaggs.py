"""
Tests for TaggedAggregates
"""
import pytest

from pcot.utils.taggedaggregates import *


#
# Basic tests with no nested types
#

def test_taggeddict():
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", str, "foo"),
        c=("c", float, 3.14)
    )

    td = tdt.create()
    assert td['a'] == 10
    assert td['b'] == "foo"
    assert td['c'] == 3.14
    assert len(td.values) == 3

    td['a'] = 20
    assert td['a'] == 20

    with pytest.raises(ValueError):
        td['a'] = "wibble"
    with pytest.raises(ValueError):
        td['a'] = 3.14
    with pytest.raises(ValueError):
        td['b'] = 64

    with pytest.raises(KeyError):
        td['d'] = 12


def test_taggedtuple():
    ttt = TaggedTupleType(
        a=("a", int, 10),
        b=("b", str, "foo"),
        c=("c", float, 3.14)
    )

    tt = ttt.create()
    assert tt[0] == 10
    assert tt[1] == "foo"
    assert tt[2] == 3.14
    assert len(tt.values) == 3

    tt[0] = 20
    assert tt[0] == 20
    # check we can set by name
    tt['a'] = 40
    # and that it actually works
    assert tt[0] == 40
    assert tt['a'] == 40
    assert tt[1] == "foo"  # make sure it's still the same otherwise
    assert tt[2] == 3.14

    with pytest.raises(ValueError):
        tt[0] = "wibble"
    with pytest.raises(ValueError):
        tt[0] = 3.14
    with pytest.raises(ValueError):
        tt[1] = 64
    # and the same with the string keys
    with pytest.raises(ValueError):
        tt['a'] = "wibble"
    with pytest.raises(ValueError):
        tt['a'] = 3.14
    with pytest.raises(ValueError):
        tt['b'] = 64


def test_taggedlist():
    tlt = TaggedListType(
        "a", int, [10, 20, 30]
    )

    tl = tlt.create()
    assert tl[0] == 10
    assert len(tl.values) == 3

    tl[0] = 60
    assert tl[0] == 60

    with pytest.raises(ValueError):
        tl[0] = "wibble"
    with pytest.raises(ValueError):
        tl[0] = 3.14

    with pytest.raises(IndexError):
        tl[9] = 12


#
# Now check that we can create nested types
#

def test_dict_of_lists():
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", TaggedListType("b", int, [10, 20, 30]), None),
        c=("c", float, 3.14)
    )

    td = tdt.create()
    assert td['a'] == 10
    assert td['b'][0] == 10
    assert td['b'][1] == 20
    assert td['b'][2] == 30
    assert td['c'] == 3.14
    assert len(td.values) == 3

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


def test_list_of_tuples():
    tlt = TaggedListType(
        "a", TaggedTupleType(
            a=("a", int, 10),
            b=("b", str, "foo"),
            c=("c", float, 3.14)),
        2
    )

    tl = tlt.create()
    assert tl[0][0] == 10
    assert tl[0][1] == "foo"
    assert tl[0][2] == 3.14
    assert tl[1][0] == 10
    assert tl[1][1] == "foo"
    assert tl[1][2] == 3.14
    assert len(tl.values) == 2

    tl[0][0] = 60
    assert tl[0][0] == 60

    with pytest.raises(ValueError):
        tl[0][0] = "wibble"
    with pytest.raises(ValueError):
        tl[0][0] = 3.14

    # here, we get value errors because the value type is checked *before* the index.
    with pytest.raises(ValueError):
        tl[9] = 12
    with pytest.raises(ValueError):  # the usual kind of error for this sort of nonsense.
        tl['frongworth'] = 12


def test_dict_of_list_of_tuples():
    tdt = TaggedDictType(
        # dictionary item A is an int
        a=("a", int, 10),
        # dictionary item B is a list of tuples (int,str,float), by default two of them.
        b=("b", TaggedListType("b", TaggedTupleType(
            a=("a", int, 10),
            b=("b", str, "foo"),
            c=("c", float, 3.14)), 2)),
        # dictionary item C is just a float
        c=("c", float, 3.14)
    )

    td = tdt.create()
    assert td['a'] == 10
    assert td['b'][0][0] == 10
    assert td['b'][0][1] == "foo"
    assert td['b'][0][2] == 3.14
    assert td['b'][1][0] == 10
    assert td['b'][1][1] == "foo"
    assert td['b'][1][2] == 3.14
    assert td['c'] == 3.14
    assert len(td.values) == 3
    assert len(td['b'].values) == 2
    assert len(td['b'][0].values) == 3

    td['b'][0][0] = 60
    assert td['b'][0][0] == 60

    with pytest.raises(ValueError):
        td['b'][0][0] = "wibble"
    with pytest.raises(ValueError):
        td['b'][0][0] = 3.14

    # here, we get value errors because the value type is checked *before* the index.
    with pytest.raises(ValueError):
        td['b'][9] = 12
    with pytest.raises(ValueError):  # the usual kind of error for this sort of nonsense.
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


def test_tuple_serialise():
    # create a simple TaggedTuple of primitives
    ttt = TaggedTupleType(
        a=("a", int, 10),
        b=("b", str, "foo"),
        c=("c", float, 3.14)
    )
    tt = ttt.create()

    # check that we can serialise it into the expected structure
    serial = tt.serialise()
    assert serial == (10, 'foo', 3.14)

    # order is important
    assert serial != (10, 3.14, 'foo')


def test_list_serialise():
    ttt = TaggedListType(
        "a", int, [10, 20, 30]
    )
    tl = ttt.create()
    serial = tl.serialise()
    assert serial == [10, 20, 30]
    assert serial != [30, 20, 10]


def test_dict_of_tuples():
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", TaggedTupleType(
            a=("a", int, 10),
            b=("b", str, "foo"),
            c=("c", float, 3.14)), None),
        b1=("b1", TaggedTupleType(
            aa=("aa", int, 20),
            bb=("bb", str, "bar"),
            cc=("c", str, "dogfish")), None),
        c=("c", float, 3.14)
    )

    td = tdt.create()
    serial = td.serialise()
    assert serial == {'c': 3.14, 'a': 10, 'b': (10, 'foo', 3.14), 'b1': (20, 'bar', 'dogfish')}
    assert serial == {'c': 3.14, 'a': 10, 'b1': (20, 'bar', 'dogfish'), 'b': (10, 'foo', 3.14)}
    assert serial != {'c': 3.14, 'a': 10, 'b': (10, 'foos', 3.14), 'b1': (20, 'bar', 'dogfish')}


def test_ser_complex():
    # a more complex structure made up of lists, dicts and tuples
    tdt = TaggedDictType(
        a=("a", int, 10),
        b=("b", TaggedListType("b", TaggedTupleType(
            a=("a", int, 10),
            b=("b", str, "foo"),
            c=("c", float, 3.14)), 2)),
        c=("c", float, 3.14),
        # a list of 4 identical dicts
        d=("d", TaggedListType("d", TaggedDictType(
            a=("a", int, 10),
            b=("b", str, "foo"),
            c=("c", float, 3.14)), 4)),
        # a list of 2 identical dicts, each with a tuple and a list inside
        e=("e", TaggedListType("e",
                               TaggedDictType(foo=("foo",
                                                   TaggedTupleType(a=("a", int, 10),
                                                                   b=("ith", str, "blungle"),
                                                                   c=("c", float, 123.4))),
                                              bar=("bar",
                                                   TaggedListType("none", int, [10, 20, 30])
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
    assert td2.type == tdt
    assert td2['a'] == 10
    assert td2['b'] == "foo"
    assert td2['c'] == 3.14


def test_tuple_ser_deser():
    ttt = TaggedTupleType(
        a=("a", int, 0),
        b=("b", str, ""),
        c=("c", float, 0.0)
    )
    serial = (10, 'foo', 3.14)

    tt2 = ttt.deserialise(serial)
    assert tt2.type == ttt
    assert tt2[0] == 10
    assert tt2[1] == "foo"
    assert tt2[2] == 3.14


def test_list_ser_deser():
    tlt = TaggedListType(
        "a", int, [0, 0, 0]
    )
    serial = [10, 20, 30]

    tl2 = tlt.deserialise(serial)
    assert tl2.type == tlt
    assert tl2[0] == 10
    assert tl2[1] == 20
    assert tl2[2] == 30


def test_dict_of_tuples_ser_deser():
    tdt = TaggedDictType(
        a=("a", int, 0),
        b=("b", TaggedTupleType(
            a=("a", int, 0),
            b=("b", str, ""),
            c=("c", float, 0.0)), None),
        b1=("b1", TaggedTupleType(
            aa=("aa", int, 0),
            bb=("bb", str, ""),
            cc=("c", str, "")), None),
        c=("c", float, 0.0)
    )
    serial = {'c': 3.14, 'a': 10, 'b': (10, 'foo', 3.14), 'b1': (20, 'bar', 'dogfish')}

    td2 = tdt.deserialise(serial)
    assert td2.type == tdt
    assert td2['a'] == 10
    assert td2['b'][0] == 10
    assert td2['b'][1] == "foo"
    assert td2['b'][2] == 3.14
    assert td2['b1'][0] == 20
    assert td2['b1'][1] == "bar"
    assert td2['b1'][2] == "dogfish"
    assert td2['c'] == 3.14


def test_complex_ser_deser():
    # a more complex structure made up of lists, dicts and tuples
    tdt = TaggedDictType(
        a=("a", int, 0),
        b=("b", TaggedListType("b", TaggedTupleType(
            a=("a", int, 0),
            b=("b", str, ""),
            c=("c", float, 0.0)), 2)),
        c=("c", float, 0.0),
        # a list of 4 identical dicts
        d=("d", TaggedListType("d", TaggedDictType(
            a=("a", int, 0),
            b=("b", str, ""),
            c=("c", float, 0.0)), 4)),
        # a list of 2 identical dicts, each with a tuple and a list inside
        e=("e", TaggedListType("e",
                               TaggedDictType(foo=("foo",
                                                   TaggedTupleType(a=("a", int, 0),
                                                                   b=("ith", str, ""),
                                                                   c=("c", float, 0.0))),
                                              bar=("bar",
                                                   TaggedListType("none", int, [])
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
    assert td2.type == tdt

    # serialise it again
    serial2 = td2.serialise()
    # check it's the same!
    assert serial2 == serial


