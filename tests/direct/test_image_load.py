import struct
import tempfile
from typing import List

import pytest

import pcot
from pcot.dataformats import load
from pcot.dataformats.raw import RawLoader
from pcot.datum import Datum

from pcot.rois import ROICircle
from pcot.utils.spectrum import SpectrumSet
from fixtures import *
from pcot.value import Value
from pcot.xform import XFormException


def test_direct_load_envi(envi_image_1):
    """Test direct input of an image cube using the dataformats.load.envi method"""

    datum = load.envi(envi_image_1)
    # get the image from the datum
    img = datum.get(Datum.IMG)

    print(datum.getSources().long())

    # note that the briefs don't have input indices because we loaded the image directly
    assert (datum.getSources().brief() == "ENVI:440&ENVI:550&ENVI:640&ENVI:800")

    # add a couple of circular ROIs to the image
    img.rois.append(ROICircle(50, 40, 4, label="a"))
    img.rois.append(ROICircle(8, 8, 4, label="b"))

    # generate a spectrum set and convert the results to a CSV table
    ss = SpectrumSet({"in": img}).table().html()
    # print
    print(ss)


def test_direct_load_envi_fail(envi_image_1):
    """Test direct input of an image cube using the dataformats.load.envi method, with a file that doesn't exist"""
    with pytest.raises(FileNotFoundError) as info:
        datum = load.envi("nonexistent_file.hdr")
    assert "nonexistent_file.hdr" in str(info.value)


def test_direct_load_rgb(globaldatadir):
    """Test direct input of an RGB image using the dataformats.load.rgb method"""

    datum = load.rgb(globaldatadir / 'rect1.png')
    # get the image from the datum
    img = datum.get(Datum.IMG)

    # note that the briefs don't have input indices because we loaded the image directly
    assert (datum.getSources().brief() == "RGB:B&RGB:G&RGB:R")

    # add a couple of circular ROIs to the image
    img.rois.append(ROICircle(10, 10, 4, label="a"))
    img.rois.append(ROICircle(8, 8, 4, label="b"))

    with pytest.raises(XFormException) as info:
        ss = SpectrumSet({"in": img}).table().html()
    assert "no single-wavelength channels in image" in str(info.value)


def test_direct_load_rgb_fail(globaldatadir):
    """Test direct input of an RGB image using the dataformats.load.rgb method, with a file that doesn't exist"""

    # may not be a FileNotFoundError - could be the format. It's just that cv.imread returns
    # None for any failure.
    with pytest.raises(Exception) as info:
        datum = load.rgb("nonexistent_file.png")
    assert "nonexistent_file.png" in str(info.value)


def test_direct_load_multifile_notfound(globaldatadir):
    """Test direct input of an image cube using the dataformats.load.multifile method, with a file that doesn't exist"""
    pcot.setup()
    with pytest.raises(FileNotFoundError) as info:
        datum = load.multifile(globaldatadir / "multi", ["1.png", "2.png", "3.png", "4.png"])
    assert "1.png" in str(info.value)


def test_direct_load_multifile_mismatch(globaldatadir):
    """Test direct input of an image cube using the dataformats.load.multifile
    method, with images of different sizes"""
    pcot.setup()
    with pytest.raises(Exception) as info:
        datum = load.multifile(globaldatadir / "multi", ["0.png", "32768.png", "65535.png", "wrongsize.png"])
    assert "all images must be the same size" in str(info.value)


def test_direct_load_multifile_nofilter(globaldatadir):
    """Test direct input of an image cube using the dataformats.load.multifile method
    but with no filter pattern specified"""
    pcot.setup()  # need to initialise a few things first - like the filter sets

    # now test the correct case but
    datum = load.multifile(globaldatadir / "multi", ["0.png", "32768.png", "65535.png"])

    # check the sources
    assert datum.getSources().brief() == "Multi:0"      # same sources will be collapsed into a single entry
    # check dimensions
    img = datum.get(Datum.IMG)
    assert img.img.shape == (30, 80, 3)
    assert img.w == 80
    assert img.h == 30
    assert img.channels == 3
    # and the data
    assert np.allclose(img.img[0, 0], (0, 32768 / 65535, 1))


def test_direct_load_multifile(globaldatadir):
    """Test direct input of an image cube using the dataformats.load.multifile method
    with the "standard" filter pattern using <lens> and <n> as the group names"""

    pcot.setup()
    names = ["FilterL02.png", "TestFilterL01image.png", "FilterR10.png"]
    datum = load.multifile(globaldatadir / "multi",
                           names,
                           filterpat=r'.*Filter(?P<lens>L|R)(?P<n>[0-9][0-9]).*')

    img = datum.get(Datum.IMG)

    # check the image and dimensions
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (32768 / 65535, 0, 1))

    for sourceSet, pos, name, cwl, fwhm, trans, desc, fn in zip(img.sources,
                                                          ('L02', 'L01', 'R10'),
                                                          ('G03', 'G04', 'S03'),
                                                          (530, 570, 450),
                                                          (15, 12, 5),
                                                          (0.957, 0.989, 0.000001356),
                                                          (None, None, None),
                                                          names,
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
        assert f.description == desc
        path = globaldatadir / "multi"
        # the long string here is a bit weird, in that it has the filenames for all the filters in always,
        # but that's because we're using the long string for the multifile input as a whole.
        assert s.long() == f"none: Cam: PANCAM, Filter: {name}({float(cwl)}nm) pos {pos}, {desc} {path / fn}"


def test_direct_load_multifile_cwl(globaldatadir):
    """Test direct input of an image cube using the dataformats.load.multifile method
    with the filter pattern using the CWL from the filename.
    """

    pcot.setup()
    names = ["F740.png", "F780.png", "F840.png"]
    datum = load.multifile(globaldatadir / "multi",
                           names,
                           filterpat=r'.*F(?P<cwl>[0-9]+).*')

    img = datum.get(Datum.IMG)

    # check the image and dimensions
    assert img.channels == 3
    assert img.w == 80
    assert img.h == 30
    assert np.allclose(img.img[0][0], (0, 1, 32768 / 65535))

    for sourceSet, pos, name, cwl, fwhm, trans, desc, fn in zip(img.sources,                  # PANCAM filter set:
                                                          ('R03', 'R02', 'R01'),        # positions
                                                          ('G07', 'G08', 'G09'),      # names
                                                          (740, 780, 840),              # cwls
                                                          (15, 20, 25),                # fwhms
                                                          (0.983, 0.981, 0.989),        # transmission ratios
                                                          (None, None, None),
                                                          names,
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
        path = globaldatadir / "multi"
        # the long string here is a bit weird, in that it has the filenames for all the filters in always,
        # but that's because we're using the long string for the multifile input as a whole.
        assert s.long() == f"none: Cam: PANCAM, Filter: {name}({float(cwl)}nm) pos {pos}, {desc} {path / fn}"


def test_direct_load_multifile_cwl_multiple_matches(globaldatadir):
    """Test direct input of an image cube using the dataformats.load.multifile method
    with the filter pattern using the CWL from the filename.
    """

    pcot.setup()
    names = ["F440.png", "F780.png", "F840.png"]
    with pytest.raises(ValueError) as info:
        datum = load.multifile(globaldatadir / "multi",
                               names,
                               filterpat=r'.*F(?P<cwl>[0-9]+).*')
    assert "Multiple matches for cwl=440" in str(info.value)
