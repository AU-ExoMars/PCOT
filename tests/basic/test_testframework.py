"""A test for the testing framework itself, and a PCOT-independent
template for other tests."""

# this is required, despite what PyCharm says.
from fixtures import *


def test_datadir(datadir):
    """Check a file exists in the data directory with the same name as
    the module but with _data added"""
    assert (datadir / 'tb.dat').is_file()
    assert not (datadir / 'tbisntthere.dat').exists()


def test_datadircontents(datadir):
    """Test that we can correctly read a file from the data directory"""
    t = (datadir / 'tb.dat').read_text(encoding='utf-8')
    assert t == "Dummy tb.dat file for testing."


def test_globaldatadir(globaldatadir):
    """Check file exists in the global data directory"""
    expected = globaldatadir / 'basn0g01.png'
    assert expected.is_file()
    unexpected = globaldatadir / 'zog.dat'
    assert not unexpected.exists()


def test_globaldatadircontents(globaldatadir):
    """Check that a file in the global data directory has the correct contents"""
    t = (globaldatadir / 'foo.dat').read_text(encoding='utf-8')
    assert t == 'Global Test Data Directory test file.'
