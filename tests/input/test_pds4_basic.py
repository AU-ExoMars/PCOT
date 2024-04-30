"""Very basic tests for PDS4 input - more work needs to be done on how PDS4 input will
work, particularly for HK data (which could be time series) and we need a corpus of known data."""
import os.path
from pathlib import Path

from proctools.products import ProductDepot

import pcot
from direct.test_image_load_pds4 import check_data
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
    doc.run()
    img = node.getOutput(0, Datum.IMG)

    # for this test, we confirm that there are 9 channels in the image we just loaded, and that
    # they have the correct source data (including LIDs).

    check_data(img, inpidx=0)
