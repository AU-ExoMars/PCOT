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
    with pytest.raises(TypeError):   # the usual kind of error for this sort of nonsense.
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
    with pytest.raises(ValueError):   # the usual kind of error for this sort of nonsense.
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
    with pytest.raises(ValueError):   # the usual kind of error for this sort of nonsense.
        td['b']['frongworth'] = 12

    with pytest.raises(KeyError):
        td['d'] = 12