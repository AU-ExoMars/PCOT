"""
Test direct PDS4 image loading. This is a separate file from the other load tests
because it requires a data set which may not be present (it's very large).
"""
import logging
import os
from pathlib import Path

import numpy as np
import pytest
import pcot
from pcot.dataformats import load
from pcot.dataformats.pds4 import PDS4External, ProductList
from pcot.datum import Datum
from proctools.products import ProductDepot

from pcot.expressions import ExpressionEvaluator
from pcot.imagecube import ChannelMapping
from pcot.rois import ROICircle
from pcot.sources import nullSource
from pcot.value import Value

testdatadir = None
try:
    testdatadir = os.path.expanduser(pcot.config.getDefaultDir("testpds4data"))
except KeyError:
    pytest.fail("testpds4data is not set in the .pcot.ini file")

if not os.path.isdir(testdatadir):
    pytest.fail(f"PDS4 test data directory {testdatadir} does not exist")


def check_data(img, inpidx=None):
    """Run some tests on the loaded PDS4 data to ensure it's been loaded correctly. This is
    a separate function so that it can be called from other tests."""

    assert img.channels == 9  # should have 9 channels
    _lids = [
        # oddly, the LIDS l04-l08 are for filter positions L01-L06 (i.e. the G filters)
        "urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l04_spec-rad_20210921t094930.245z",
        "urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l05_spec-rad_20210921t095008.245z",
        "urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l06_spec-rad_20210921t095046.246z",
        "urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l07_spec-rad_20210921t095128.246z",
        "urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l08_spec-rad_20210921t095204.246z",
        "urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l09_spec-rad_20210921t095237.246z",
        # then the RGB filters l01-03 follow those.
        "urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l01_spec-rad_20210921t101213.046z",
        "urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l02_spec-rad_20210921t101251.046z",
        "urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l03_spec-rad_20210921t101327.048z",
    ]

    # these are filter data - we need to check that the filter data is correct.
    # The data is in the form (cwl, fwhm, transmission, position, name)
    testSet = [
        (570, 12, .989, "L01", "G04"),
        (530, 15, .957, "L02", "G03"),
        (610, 10, .956, "L03", "G05"),
        (500, 20, .966, "L04", "G02"),
        (670, 12, .962, "L05", "G06"),
        (440, 25, .987, "L06", "G01"),
        (640, 100, .993, "L07", "C01L"),
        (540, 80, .988, "L08", "C02L"),
        (440, 120, .983, "L09", "C03L"),
    ]

    # combine those two sets (lids and filters)
    testSet = [(x,) + y for x, y in zip(_lids, testSet)]
    # now sort that by cwl and fwhm (which is what the input method will do)
    testSet.sort(key=lambda x: (x[1], x[2]))
    # and prepend the image sources which is what we're testing against
    testSet = [(x,) + y for x, y in zip(img.sources, testSet)]

    for sourceSet, lid, cwl, fwhm, tr, pos, name in testSet:
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.getFilter()
        # and the filter data should be correct, and sorted by capture time which happens to be
        # filter position.
        assert f.cwl == cwl
        assert f.fwhm == fwhm
        assert f.name == name

        # These will be wrong because PDS4 doesn't hold this data!!!

        # this is what they should be
        # assert f.position == pos
        # assert f.transmission == tr

        assert f.transmission == 1.0
        assert f.position == name

        assert isinstance(s.external, PDS4External)
        p = s.external.product
        assert p.lid == lid
        inpname = str(inpidx) if inpidx is not None else "NI"  # "NI" = no input
        assert s.debug() == f'{inpname},pds4({lid[:20]}),{cwl}'
        # I'm not testing the long form of the descriptor, because it's too long probably subject to change.


def test_pds4_load_from_dplist():
    """Use the proctools depot to load a PDS4 image from a DataProduct list"""
    depot = ProductDepot()
    depot.load(Path(testdatadir), recursive=True)
    specrads = [x for x in depot.retrieve("spec-rad") if x.meta.camera == 'WACL']
    assert len(specrads) == 9  # 9 left hand camera images

    d = load.pds4(specrads)  # passing a list of data products
    img = d.get(Datum.IMG)
    check_data(img)


def test_pds4_load_from_productlist():
    """Try to load PDS4 image from a ProductList"""
    depot = ProductDepot()
    depot.load(Path(testdatadir), recursive=True)
    specrads = [x for x in depot.retrieve("spec-rad") if x.meta.camera == 'WACL']
    assert len(specrads) == 9  # 9 left hand camera images

    p = ProductList(specrads)  # pass a list of DataProducts to ProductList ctor

    d = load.pds4(p)  # passing a list of data products
    img = d.get(Datum.IMG)
    check_data(img)


def test_pds4_load_from_stringlist():
    """Try to load PDS4 image from a list of strings"""

    # get a list of the files in the test data directory which are LWAC images
    filenames = [str(x) for x in Path(testdatadir).glob("*l0*.xml")]
    assert len(filenames) == 9

    d = load.pds4(filenames)  # passing a list of data products
    img = d.get(Datum.IMG)
    check_data(img)
