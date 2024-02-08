"""Very basic tests for PDS4 input - more work needs to be done on how PDS4 input will
work, particularly for HK data (which could be time series) and we need a corpus of known data."""
import os.path
from pathlib import Path

from proctools.products import ProductDepot

import pcot
from pcot.dataformats.pds4 import PDS4External

from pcot.datum import Datum
from pcot.document import Document
import pytest


def test_pds4_load():
    """Load some PDS4 data, check the channel count in the result, the LIDs, the filter properties
    but NOT the image pixels (we need a small test image for that)"""
    
    pcot.setup()
    doc = Document()

    # this won't work at all if the link to a test data directory isn't found. I don't want
    # to check that data in, it's enormous. The test data should currently be rcp_output (which can
    # be found on the AU_ExoMars sharepoint). You should set this in your .pcot.ini file in your
    # home directory.

    try:
        testdatadir = os.path.expanduser(pcot.config.getDefaultDir("testpds4data"))
    except KeyError:
        pytest.fail("testpds4data is not set in the .pcot.ini file")
    if not os.path.isdir(testdatadir):
        pytest.fail(f"PDS4 test data directory {testdatadir} does not exist")

    # PDS4 input works through proctools; load the products.
    depot = ProductDepot()
    depot.load(Path(testdatadir), recursive=True)

    # grab a particular product type
    specrads = [x for x in depot.retrieve("spec-rad") if x.meta.camera == 'WACL']
    assert len(specrads) == 9  # 9 left hand camera images
    doc.setInputPDS4(0, specrads)

    node = doc.graph.create("input 0")
    doc.changed()
    img = node.getOutput(0, Datum.IMG)

    # for this test, we confirm that there are 9 channels in the image we just loaded, and that
    # they have the correct source data (including LIDs).

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

    # combine those two sets
    testSet = [(x,)+y for x, y in zip(_lids, testSet)]
    # now sort that by cwl and fwhm (which is what the input method will do)
    testSet.sort(key=lambda x: (x[1], x[2]))
    # and prepend the image sources which is what we're testing against
    testSet = [(x,)+y for x, y in zip(img.sources, testSet)]

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
        assert s.debug() == f'0,pds4({lid[:20]}),{cwl}'
        # I'm not testing the long form of the descriptor, because it's too long probably subject to change.
