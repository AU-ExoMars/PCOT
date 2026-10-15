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
    # value should have been given to the config's sigfigs (5 in tests) and stringified
    assert "1.2346" in lines[3]
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


def test_table_float_formatting(monkeypatch):
    """Floats are written to the config's significant figures, so small values aren't lost, but large
    values never lose digits before the decimal point or go into scientific notation"""
    import pcot.config
    t = Table()
    t.newRow()
    for k, v in [("small", 0.0000123456), ("tiny", 1.23456789e-7), ("mid", 2.00938), ("big", 123456.789),
                 ("carry", 99999.5), ("zero", 0.0), ("f32", np.float32(1.23456)), ("int", 7)]:
        t.add(k, v)
    assert str(t).splitlines()[1] == "1.2346e-05,1.2346e-07,2.0094,123457,99999.5,0,1.2346,7"

    monkeypatch.setattr(pcot.config.data, "sigfigs", 3)
    assert str(t).splitlines()[1] == "1.23e-05,1.23e-07,2.01,123457,99999.5,0,1.23,7"
