"""Very basic tests for PDS4 input - more work needs to be done on how PDS4 input will
work, particularly for HK data (which could be time series) and we need a corpus of known data."""
import os.path
from pathlib import Path

from proctools.products import ProductDepot

import pcot

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

    for sourceSet, pos, name, cwl, fwhm, tr, lid in zip(img.sources,
                                                        ('L01', 'L02', 'L03', 'L04', 'L05', 'L06', 'L07', 'L08', 'L09'),
                                                        ('G04', 'G03', 'G05', 'G02', 'G06', 'G01', 'C01L', 'C02L',
                                                         'C03L'),
                                                        (570, 530, 610, 500, 670, 440, 640, 540, 440),
                                                        (12, 15, 10, 20, 12, 25, 100, 80, 120),
                                                        (0.989, 0.957, 0.956, 0.966, 0.962, 0.987, 0.993, 0.988, 0.983),
                                                        _lids
                                                        ):
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        f = s.filterOrName
        # and the filter data should be correct, and sorted by capture time which happens to be
        # filter position.
        assert f.cwl == cwl
        assert f.fwhm == fwhm
        assert f.name == name
        assert f.position == pos
        assert f.transmission == tr
        assert s.getPDS4() is not None
        assert s.getPDS4().lid == lid
        assert s.brief() == f'0:{cwl}'
        assert s.long() == f"PDS4-0: wavelength {cwl}, fwhm {fwhm} {s.getPDS4().lid}"
