import shutil
import tempfile
from datetime import datetime
from tempfile import TemporaryDirectory

import pcot
from fixtures import *
from pcot.datum import Datum
from pcot.document import Document
from pcot.sources import nullSourceSet
from pcot.utils.archive import FileArchive
from pcot.utils.datumstore import DatumStore
from pcot.value import Value
import pcot.datumfuncs as df


def test_create():
    """Basic smoke test - can we make a PARC file, shove a couple of scalars in it, and get them out?"""
    with tempfile.TemporaryDirectory() as td:
        fn = td + "/eek.parc"

        # open for writing, must be inside a context manager
        with FileArchive(fn, 'w') as a:
            da = DatumStore(a)
            d = Datum.k(10, 0.2, dq.TEST)
            da.writeDatum("test", d)
            d = Datum.k(11, 0.7, dq.TEST)
            da.writeDatum("test2", d)

        # open for reading, must be outside a context manager
        a = DatumStore(FileArchive(fn), 1000)

        d = a.get("test", None)
        assert Value(10, 0.2, dq.TEST) == d.get(Datum.NUMBER)
        d = a.get("test2", None)
        assert Value(11, 0.7, dq.TEST) == d.get(Datum.NUMBER)


def test_cache():
    """Test basic cache behaviour using the read_count attribute"""
    with tempfile.TemporaryDirectory() as td:
        fn = td + "/eek.parc"

        # open for writing, must be inside a context manager - but here we're
        # not using a context manager for the store, we're explicitly calling
        # writeManifest.
        with FileArchive(fn, 'w') as a:
            a = DatumStore(a, 1000)
            d = Datum.k(10, 0.2, dq.TEST)
            a.writeDatum("test", d)
            d = Datum.k(11, 0.7, dq.TEST)
            a.writeDatum("test2", d)
            a.writeManifest()

        # open for reading, must be outside a context manager
        a = DatumStore(FileArchive(fn), 1000)

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
        fn = td + "/eek.parc"

        # open for writing, must be inside a context manager
        with FileArchive(fn, 'w') as a:
            da = DatumStore(a)
            da.writeDatum("test", d)
            da.writeDatum("test2", d2)

        # open for reading, must be outside a context manager
        a = DatumStore(FileArchive(fn), 7000)

        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0, 0] == (Value(0), Value(1), Value(0))

        d = a.get("test2", doc)
        img = d.get(Datum.IMG)
        assert img[0, 0] == (Value(0), Value(1), Value(1))

        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0, 0] == (Value(0), Value(1), Value(0))

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
        fn = td + "/eek.parc"

        # open for writing, must be inside a context manager
        with FileArchive(fn, 'w') as a:
            da = DatumStore(a)
            da.writeDatum("test", d)
            da.writeDatum("test2", d2)
            da.writeDatum("test3", d3)

        # open for reading, must be outside a context manager
        a = DatumStore(FileArchive(fn), 7000)     # cache size enough for 2 items?

        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0, 0] == (Value(0), Value(1), Value(0))

        d = a.get("test2", doc)
        img = d.get(Datum.IMG)
        assert img[0, 0] == (Value(0), Value(1), Value(1))

        d = a.get("test2", doc)
        img = d.get(Datum.IMG)
        assert img[0, 0] == (Value(0), Value(1), Value(1))

        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0, 0] == (Value(0), Value(1), Value(0))

        assert a.read_count == 2
        snark = a.total_size()

        # reading another image should cause a discard
        d = a.get("test3", doc)
        img = d.get(Datum.IMG)
        assert img[0, 0] == (Value(1), Value(0), Value(1))
        assert a.read_count == 3

        # but "test" should be OK because it's still recent
        d = a.get("test", doc)
        img = d.get(Datum.IMG)
        assert img[0, 0] == (Value(0), Value(1), Value(0))
        assert a.read_count == 3


def test_vector_and_cache():
    pcot.setup()
    doc = Document()

    with tempfile.TemporaryDirectory() as td:
        fn = td + "/eek.parc"

        # open for writing, must be inside a context manager
        with FileArchive(fn, 'w') as fa:
            a = DatumStore(fa)
            vec = np.linspace(0, 1, 1000)
            d = Datum(Datum.NUMBER, Value(vec, 0.1, dq.TEST), sources=nullSourceSet)
            a.writeDatum("test0", d)

            vec = np.linspace(1, 10, 1000)
            d = Datum(Datum.NUMBER, Value(vec, 0.1, dq.TEST), sources=nullSourceSet)
            a.writeDatum("test1", d)

            vec = np.linspace(2, 100, 1000)
            d = Datum(Datum.NUMBER, Value(vec, 0.1, dq.TEST), sources=nullSourceSet)
            a.writeDatum("test2", d)

            print(d.getSize())

        a = DatumStore(FileArchive(fn), 20000)  # enough for two of the vectors
        d = a.get("test0", doc)
        assert np.allclose(d.get(Datum.NUMBER).n, np.linspace(0, 1, 1000))
        assert np.allclose(d.get(Datum.NUMBER).u, 0.1)
        assert d.get(Datum.NUMBER).u.shape == (1000,)

        d = a.get("test1", doc)
        assert np.allclose(d.get(Datum.NUMBER).n, np.linspace(1, 10, 1000))

        d = a.get("test2", doc)
        assert np.allclose(d.get(Datum.NUMBER).n, np.linspace(2, 100, 1000))

        a.get("test1", doc)  # should not require a read
        assert a.read_count == 3

        a.get("test0", doc)  # will require a read, will no longer be cached
        assert a.read_count == 4


def test_datumstore_append(globaldatadir):
    """Test we can append to a datum store. First, we should copy an existing test store"""

    with TemporaryDirectory() as tmpdir:
        # copy the test archive into a new archive onto which we will append
        newarchive = os.path.join(tmpdir, "newarchive.dat")
        shutil.copyfile(globaldatadir / "parc/multi.parc", newarchive)

        # first we'll open the archive for reading to get some stuff from it. We can't read from
        # an archive opened for append. Note that we're not using a context manager for the FileArchive
        # here, only for the DatumStore. That means the FileArchive will be closed when the DatumStore
        # is created, so the DatumStore opens the FileArchive.

        a = DatumStore(FileArchive(newarchive, 'r'))
        img1 = a.get("image0", None)
        img2 = a.get("image1", None)

        # combine those images into a third
        img3 = img1 + img2
        assert img3.tp == Datum.IMG
        # and get a vector of the means of its channels
        means = df.mean(img3)

        # here, though, we are using context managers for both.
        with FileArchive(newarchive, 'a') as fa:
            a = DatumStore(fa)
            # now append that image and the vector of means
            a.writeDatum("combined", img3, "images 0 and 1 combined")
            a.writeDatum("combinedmeans", means, "means of combined image channels")

        # that done, open for reading.
        a = DatumStore(FileArchive(newarchive, 'r'))
        img3 = a.get("combined", None)
        means = a.get("combinedmeans", None)
        assert img3.tp == Datum.IMG
        assert means.tp == Datum.NUMBER
        img = img3.get(Datum.IMG)
        assert img.shape == (256, 256, 3)

        # check the info in the manifest is correct
        info = a.getMetadata("combined")
        assert info.datumtype == 'img'
        assert info.description == "images 0 and 1 combined"
        delta = datetime.now() - info.created
        assert delta.total_seconds() < 20


def test_manifest_read(globaldatadir):
    """Test we can read item info from the manifest"""
    a = DatumStore(FileArchive(globaldatadir / "parc/multi.parc"))
    assert len(a.getManifest()) == 14

    m = a.getMetadata("image0")
    assert m is not None
    assert m.datumtype == 'img'
    assert m.description == 'testimg(0)'

    m = a.getMetadata("testvec1")
    assert m is not None
    assert m.datumtype == 'number'
    assert m.description == '0-2, 200 numbers'
    tt = datetime.fromisoformat("2024-11-20")
    delta = m.created - tt
    assert delta.days < 1
