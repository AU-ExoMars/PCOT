"""Multifile input tests"""
import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *
from pcot.filters import Filter


def test_multifile_load_with_default_pattern(globaldatadir):
    """Load up a set of images using the default filter pattern, which will give duff sources"""
    pcot.setup()
    doc = Document()

    # having created a document, set an input. Try one that doesn't exist first.
    v = doc.setInputMulti(0, str(globaldatadir / "dirdoesntexist"), ["1.png", "2.png", "3.png", "4.png"])
    assert v.startswith('Cannot read file')
    v = doc.setInputMulti(0, str(globaldatadir / "multi"), ["0.png", "zzzz2.png", "32768.png", "65535.png"])
    assert v.startswith('Cannot read file') and 'zzzz2' in v
    # this won't load because of a size mismatch
    v = doc.setInputMulti(0, str(globaldatadir / "multi"), ["0.png", "32768.png", "65535.png", "wrongsize.png"])
    assert v == "all images must be the same size in a multifile"

    # this should load, but the sources are going to be a complete mess.
    names = ["0.png", "32768.png", "65535.png"]
    assert doc.setInputMulti(0, str(globaldatadir / "multi"), names) is None

    node = doc.graph.create("input 0")
    doc.changed()
    img = node.getOutput(0, Datum.IMG)

    # check the image
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (0, 32768 / 65535, 1))

    # check the sources, such as they are
    assert len(img.sources) == 3
    for i, sourceSet in enumerate(img.sources):
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        print(s.long())
        # if we haven't got a good regex to extract the filter data, multifile will extract dummy data.
        assert f.cwl == 0
        assert f.fwhm == 0
        assert f.name == '??'
        assert f.position == '??'
        assert f.transmission == 1
        path = str(globaldatadir / "multi" / names[i])
        # starts with zero because this is for input 0
        assert s.long() == f"0: wavelength 0, fwhm 0 {path}"


def test_multifile_load_with_bad_pattern(globaldatadir):
    """Load up a set of images using a uncompilable pattern"""
    pcot.setup()
    doc = Document()

    # this should load, but the sources are going to be a complete mess, and the filter pattern is hopeless.
    assert doc.setInputMulti(0, str(globaldatadir / "multi"), ["0.png", "32768.png", "65535.png"],
                             filterpat='[') is None

    node = doc.graph.create("input 0")
    doc.changed()
    img = node.getOutput(0, Datum.IMG)

    # check the image
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (0, 32768 / 65535, 1))

    for sourceSet in img.sources:
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        # again, the filters will be "I have no idea"
        assert f.cwl == 0
        assert f.fwhm == 0
        assert f.name == '??'
        assert f.position == '??'
        assert f.transmission == 1


def test_multifile_load_with_good_pattern(globaldatadir):
    """Here we set up a custom pattern to work out filter positions from file names, assuming that these are PANCAM
    filters."""
    pcot.setup()
    doc = Document()

    # The pattern is things like ...FilterL09.. for filter left-9.
    filenames = ["FilterL02.png", "TestFilterL01image.png", "FilterR10.png"]
    assert doc.setInputMulti(0, str(globaldatadir / "multi"),
                             filenames,
                             filterpat=r'.*Filter(?P<lens>L|R)(?P<n>[0-9][0-9]).*') is None

    node = doc.graph.create("input 0")
    doc.changed()
    img = node.getOutput(0, Datum.IMG)

    # check the image
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (32768 / 65535, 0, 1))

    path = globaldatadir / "multi"

    # pancam filters L02, L01, R10.
    for sourceSet, pos, name, cwl, fwhm, trans, fn in zip(img.sources,
                                                        ('L02', 'L01', 'R10'),
                                                        ('G03', 'G04', 'S03'),
                                                        (530, 570, 450),
                                                        (15, 12, 5),
                                                        (0.957, 0.989, 0.000001356),
                                                        filenames,
                                                      ):
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        # again, the filters will be "I have no idea"
        assert f.cwl == cwl
        assert f.fwhm == fwhm
        assert f.name == name
        assert f.position == pos
        assert f.transmission == trans
        qq = s.long()
        # the long string here is a bit weird, in that it has the filenames for all the filters in always,
        # but that's because we're using the long string for the multifile input as a whole.
        assert s.long() == f"0: wavelength {cwl}, fwhm {fwhm} {path / fn}"


def test_multifile_load_with_cwl(globaldatadir):
    pcot.setup()
    doc = Document()

    # This looks for a wavelength
    filenames = ["F440.png", "F540.png", "F640.png"]
    assert doc.setInputMulti(0, str(globaldatadir / "multi"),
                             filenames,
                             filterpat=r'.*F(?P<cwl>[0-9]+).*') is None

    node = doc.graph.create("input 0")
    doc.changed()
    img = node.getOutput(0, Datum.IMG)

    # check the image
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (0, 1, 32768 / 65535))

    path = str(globaldatadir / "multi")
    filenames = ", ".join([f"{i}: {s}" for i, s in enumerate(filenames)])

    for sourceSet, pos, name, cwl, fwhm, trans, fn in zip(img.sources,
                                                        ('L06', 'L08', 'L07'),
                                                        ('G01', 'C02L', 'C01L'),
                                                        (440, 540, 640),
                                                        (25, 80, 100),
                                                        (0.987, 0.988, 0.993),
                                                        filenames,
                                                      ):
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        # again, the filters will be "I have no idea"
        assert f.cwl == cwl
        assert f.fwhm == fwhm
        assert f.name == name
        assert f.position == pos
        assert f.transmission == trans

