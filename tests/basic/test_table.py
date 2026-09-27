"""Tests for pcot.utils.table.Table"""

import numpy as np

from pcot.utils.table import Table


def test_table_text_basic():
    """text() should produce header and data rows justified to column widths"""
    t = Table()
    t.newRow("row1")
    t.add("a", "x")
    t.add("b", "yy")
    t.newRow("row2")
    t.add("a", "zzz")
    t.add("b", "w")

    out = t.text()
    lines = out.splitlines()
    # top rule, header, rule, then the two data rows
    assert len(lines) == 5
    assert "a" in lines[1] and "b" in lines[1]
    assert "x" in lines[3] and "yy" in lines[3]
    assert "zzz" in lines[4] and "w" in lines[4]


def test_table_text_numpy_float32():
    """text() should not raise TypeError when a cell holds a numpy.float32 value

    (regression test: colwidths used to be calculated with len(v) on the raw
    value rather than a stringified/rounded one, which blows up for numeric
    types such as numpy.float32 that have no len())
    """
    t = Table()
    t.newRow("row1")
    t.add("a", np.float32(1.23456))
    t.add("b", "label")

    out = t.text()
    lines = out.splitlines()
    assert len(lines) == 4
    # value should have been rounded to the table's sigfigs (default 5) and stringified
    assert str(round(np.float32(1.23456), t.sigfigs)) in lines[3]
    assert "label" in lines[3]


def test_table_text_mixed_types_and_titletext():
    """text() should handle a mix of int, float, np.float32 and str cells, and a title"""
    t = Table()
    t.newRow("row1")
    t.add("i", 42)
    t.add("f", 3.14159265)
    t.add("nf", np.float32(2.71828))
    t.add("s", "hello")

    out = t.text(titletext="mytitle")
    lines = out.splitlines()
    assert lines[0].startswith("===mytitle")
    assert "42" in lines[3]
    assert "hello" in lines[3]
