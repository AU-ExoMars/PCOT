"""
Simple tests of the archive system.
"""
import shutil
from pathlib import Path
from fixtures import *
from tempfile import TemporaryDirectory
import os

import numpy as np

from pcot.utils.archive import MemoryArchive, FileArchive

test_data_d1 = {
    "foo": 1,
    "bar": "hello",
    "baz": np.array([1, 2, 3])
}

test_data_d2 = {
    "foo": 2,
    "bar": "world",
    "baz": np.array([4, 5, 6]),
    "lst": [1, 2, 3],
    "d": {
        "a": 1,
        "b": 2,
        "c": [1, 2, 3],
        "d": np.array([10, 20, 30, 40]).reshape(2, 2)
    }
}


def d1_correct(d1a):
    # can't just use == on the entire dicts because of the embedded numpy arrays
    assert d1a["foo"] == 1
    assert d1a["bar"] == "hello"
    assert np.all(d1a["baz"] == np.array([1, 2, 3]))


def d2_correct(d2a):
    assert d2a["foo"] == 2
    assert d2a["bar"] == "world"
    assert np.all(d2a["baz"] == np.array([4, 5, 6]))
    assert d2a["lst"] == [1, 2, 3]
    assert d2a["d"]["a"] == 1
    assert d2a["d"]["b"] == 2
    assert np.all(d2a["d"]["c"] == np.array([1, 2, 3]))
    assert np.all(d2a["d"]["d"] == np.array([10, 20, 30, 40]).reshape(2, 2))


def test_mem_archive():
    """This test will write two blocks of JSON to a MemoryArchive. Fundamentally
    we can only store JSON-serialisable data and numpy arrays (but the root must
    be a normal JSON-serialisable)."""

    # no argument, it's in write mode
    with MemoryArchive() as a:
        a.writeJson("block1", test_data_d1)
        a.writeJson("block2", test_data_d2)
        data = a.get()

    with MemoryArchive(data) as a:
        d1a = a.readJson("block1")
        d2a = a.readJson("block2")

    d1_correct(d1a)
    d2_correct(d2a)


def test_file_archive_write_read():
    """Similar using a file archive in a temporary directory"""

    with TemporaryDirectory() as tmpdir:
        fn = os.path.join(tmpdir, "test_archive")
        with FileArchive(Path(fn), "w") as a:
            a.writeJson("block1", test_data_d1)
            a.writeJson("block2", test_data_d2)

        with FileArchive(Path(fn), "r") as a:
            d1a = a.readJson("block1")
            d2a = a.readJson("block2")

            d1_correct(d1a)
            d2_correct(d2a)


def test_file_archive_nonexistent():
    """Test that a nonexistent file is handled correctly"""

    with pytest.raises(FileNotFoundError):
        with FileArchive(Path("nonexistent.dat"), "r") as a:
            pass


def test_file_archive_premade(globaldatadir):
    with FileArchive(globaldatadir / "parc/testarch.dat") as a:
        d1a = a.readJson("data1")
        d2a = a.readJson("data2")

        d1_correct(d1a)
        d2_correct(d2a)


def test_file_append_in_place(globaldatadir):
    with TemporaryDirectory() as tmpdir:
        # copy the test archive into a new archive onto which we will append
        newarchive = os.path.join(tmpdir, "newarchive.dat")
        shutil.copyfile(globaldatadir / "parc/testarch.dat", newarchive)

        # open the archive for append-in-place
        with FileArchive(Path(newarchive), "A") as a:
            # append some data
            dd = {"a": 1, "b": 2, "c": np.array([4, 3, 2, 1])}
            a.writeJson("newdata", dd)

        # now read it back
        with FileArchive(Path(newarchive), "r") as a:
            d1a = a.readJson("data1")
            d2a = a.readJson("data2")
            d3a = a.readJson("newdata")

            d1_correct(d1a)
            d2_correct(d2a)
            assert d3a["a"] == 1
            assert d3a["b"] == 2
            assert np.all(d3a["c"] == np.array([4, 3, 2, 1]))


def test_file_append_not_in_place(globaldatadir):
    with TemporaryDirectory() as tmpdir:
        # copy the test archive into a new archive onto which we will append
        newarchive = os.path.join(tmpdir, "newarchive.dat")
        shutil.copyfile(globaldatadir / "parc/testarch.dat", newarchive)

        # open the archive for append-in-place
        with FileArchive(Path(newarchive), "a") as a:
            # append some data
            dd = {"a": 1, "b": 2, "c": np.array([4, 3, 2, 1])}
            a.writeJson("newdata", dd)

        # now read it back
        with FileArchive(Path(newarchive), "r") as a:
            d1a = a.readJson("data1")
            d2a = a.readJson("data2")
            d3a = a.readJson("newdata")

            d1_correct(d1a)
            d2_correct(d2a)
            assert d3a["a"] == 1
            assert d3a["b"] == 2
            assert np.all(d3a["c"] == np.array([4, 3, 2, 1]))


def test_file_append_not_in_place_error(globaldatadir):
    """Make sure that an error doesn't result in the file being appended to getting
    corrupted"""

    with TemporaryDirectory() as tmpdir:
        # copy the test archive into a new archive onto which we will append
        newarchive = os.path.join(tmpdir, "newarchive.dat")
        shutil.copyfile(globaldatadir / "parc/testarch.dat", newarchive)

        # get the modified date of the new file.
        newarchive_mtime = os.path.getmtime(newarchive)

        # sleep for a couple of seconds.
        import time
        time.sleep(2)

        # open the archive for append-in-place, but this time it will fail.
        # The modified date of the file should not change because it should
        # never be overwritten.
        with pytest.raises(Exception):
            with FileArchive(Path(newarchive), "a") as a:
                # append some data
                dd = {"a": 1, "b": 2, "c": np.array([4, 3, 2, 1])}
                a.writeJson("data1", dd)

        # now read it back; the new data will not be there.
        with FileArchive(Path(newarchive), "r") as a:
            d1a = a.readJson("data1")
            d2a = a.readJson("data2")
            with pytest.raises(KeyError):
                d3a = a.readJson("newdata")

            d1_correct(d1a)
            d2_correct(d2a)

        # check the timestamp is unchanged because the file was not
        # copied back.
        assert os.path.getmtime(newarchive) == newarchive_mtime


def test_duplicate_name():
    """Test that writing the same item twice raises an exception"""

    # first in a memory archive
    with MemoryArchive() as a:
        a.writeJson("block1", test_data_d1)
        with pytest.raises(Exception):
            a.writeJson("block1", test_data_d2)

    # now in a file archive
    with TemporaryDirectory() as tmpdir:
        fn = os.path.join(tmpdir, "test_archive")
        with FileArchive(Path(fn), "w") as a:
            a.writeJson("block1", test_data_d1)
            with pytest.raises(Exception):
                a.writeJson("block1", test_data_d2)