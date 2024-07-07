import tempfile

import pcot
from fixtures import genrgb
from pcot import dq
from pcot.datum import Datum
from pcot.document import Document
from pcot.utils.archive import FileArchive
from pcot.utils.datumarchive import DatumArchive
from pcot.value import Value


def test_create():
    """Basic smoke test - can we make a DatumArchive, shove a couple of scalars in it, and get them out?"""
    with tempfile.TemporaryDirectory() as td:
        fn = td + "/eek.pcot"

        # open for writing, must be inside a context manager
        with FileArchive(fn, 'w') as a:
            a = DatumArchive(a, 1000)
            d = Datum.k(10, 0.2, dq.TEST)
            a.writeDatum("test", d)
            d = Datum.k(11, 0.7, dq.TEST)
            a.writeDatum("test2", d)

        # open for reading, must be outside a context manager
        a = DatumArchive(FileArchive(fn), 1000)

        d = a.get("test", None)
        assert Value(10, 0.2, dq.TEST) == d.get(Datum.NUMBER)
        d = a.get("test2", None)
        assert Value(11, 0.7, dq.TEST) == d.get(Datum.NUMBER)


def test_cache():
    """Test basic cache behaviour using the read_count attribute"""
    with tempfile.TemporaryDirectory() as td:
        fn = td + "/eek.pcot"

        # open for writing, must be inside a context manager
        with FileArchive(fn, 'w') as a:
            a = DatumArchive(a, 1000)
            d = Datum.k(10, 0.2, dq.TEST)
            a.writeDatum("test", d)
            d = Datum.k(11, 0.7, dq.TEST)
            a.writeDatum("test2", d)

        # open for reading, must be outside a context manager
        a = DatumArchive(FileArchive(fn), 1000)

        d = a.get("test", None)
        assert Value(10, 0.2, dq.TEST) == d.get(Datum.NUMBER)
        assert a.read_count == 1

        d = a.get("test", None)
        assert Value(10, 0.2, dq.TEST) == d.get(Datum.NUMBER)
        assert a.read_count == 1

        d = a.get("test2", None)
        assert Value(11, 0.7, dq.TEST) == d.get(Datum.NUMBER)
        assert a.read_count == 2

        d = a.get("test2", None)
        assert Value(11, 0.7, dq.TEST) == d.get(Datum.NUMBER)
        assert a.read_count == 2

        d = a.get("test", None)
        assert Value(10, 0.2, dq.TEST) == d.get(Datum.NUMBER)
        assert a.read_count == 2

        d = a.get("test", None)
        assert Value(10, 0.2, dq.TEST) == d.get(Datum.NUMBER)
        assert a.read_count == 2

        d = a.get("test2", None)
        assert Value(11, 0.7, dq.TEST) == d.get(Datum.NUMBER)
        assert a.read_count == 2

        d = a.get("test2", None)
        assert Value(11, 0.7, dq.TEST) == d.get(Datum.NUMBER)
        assert a.read_count == 2


def test_image():
    """
    Test we can store and get images
    """
    pcot.setup()
    doc = Document()

    img = genrgb(10, 10, 0, 1, 0)
    d = Datum(Datum.IMG, img)

    img2 = genrgb(10, 10, 0, 1, 1)
    d2 = Datum(Datum.IMG, img2)

    with tempfile.TemporaryDirectory() as td:
        fn = td + "/eek.pcot"

        # open for writing, must be inside a context manager
        with FileArchive(fn, 'w') as a:
            a = DatumArchive(a, 10000)
            a.writeDatum("test", d)
            a.writeDatum("test2", d2)

        # open for reading, must be outside a context manager
        a = DatumArchive(FileArchive(fn), 7000)

        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0,0] == (Value(0), Value(1), Value(0))

        d = a.get("test2", doc)
        img = d.get(Datum.IMG)
        assert img[0,0] == (Value(0), Value(1), Value(1))

        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0,0] == (Value(0), Value(1), Value(0))

        assert a.read_count == 2


def test_cache_discard():
    """
    Test we can store and get images, and that we can drop old images from the cache
    """
    pcot.setup()
    doc = Document()

    img = genrgb(10, 10, 0, 1, 0)
    d = Datum(Datum.IMG, img)

    img2 = genrgb(10, 10, 0, 1, 1)
    d2 = Datum(Datum.IMG, img2)

    img3 = genrgb(10, 10, 1, 0, 1)
    d3 = Datum(Datum.IMG, img3)

    with tempfile.TemporaryDirectory() as td:
        fn = td + "/eek.pcot"

        # open for writing, must be inside a context manager
        with FileArchive(fn, 'w') as a:
            a = DatumArchive(a, 10000)
            a.writeDatum("test", d)
            a.writeDatum("test2", d2)
            a.writeDatum("test3", d3)

        # open for reading, must be outside a context manager
        a = DatumArchive(FileArchive(fn), 7000)

        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0,0] == (Value(0), Value(1), Value(0))

        d = a.get("test2", doc)
        img = d.get(Datum.IMG)
        assert img[0,0] == (Value(0), Value(1), Value(1))

        d = a.get("test2", doc)
        img = d.get(Datum.IMG)
        assert img[0,0] == (Value(0), Value(1), Value(1))

        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0,0] == (Value(0), Value(1), Value(0))

        assert a.read_count == 2

        # reading another image should cause a discard
        d = a.get("test3", doc)
        img = d.get(Datum.IMG)
        assert img[0,0] == (Value(1), Value(0), Value(1))
        assert a.read_count == 3

        # but "test" should be OK because it's still recent
        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0,0] == (Value(0), Value(1), Value(0))
        assert a.read_count == 3
