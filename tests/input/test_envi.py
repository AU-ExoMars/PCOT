"""Tests of the ENVI input method"""

import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *
from pcot.filters import Filter
from pcot.inputs.envimethod import ENVIInputMethod


def test_envi_load(envi_image_1):
    """Check we can load an ENVI - check the image values and filter names"""
    pcot.setup()
    doc = Document()
    # having created a document, set an input. Try one that doesn't exist first.
    assert doc.setInputENVI(0, "thisfiledoesntexist234234") == 'Cannot read file thisfiledoesntexist234234'
    assert doc.setInputENVI(0, envi_image_1) is None  # now try the right one

    # create a document with just an input node in it, to bring that input into the document's graph
    node = doc.graph.create("input 0")
    # notify the document changed
    doc.run()
    # and get the output of the node, which should be the image loaded from the ENVI
    img = node.getOutput(0, Datum.IMG)
    # check the basic stats
    assert img.channels == 4
    assert img.w == 80
    assert img.h == 60

    # check the sources.
    assert len(img.sources) == 4
    for sourceSet in img.sources:
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = img.sources.sourceSets[0].getOnlyItem()
        # and that it's from input 0, and that it's attached to a Filter
        assert s.inputIdx == 0
        assert s.getFilter() is not None
    # now check the filter frequencies and names
    for ss, cwl, idx in zip(img.sources, (800, 640, 550, 440), (1, 2, 3)):
        s = ss.getOnlyItem()
        f = s.getFilter()
        assert f.cwl == cwl
        assert f.name == f"L{idx}_{cwl}"        # gen_envi generates names in the form Ln_cwl, n starts at 1
        assert f.position == f"L{idx}_{cwl}"
        assert f.fwhm == 25                     # gen_envi sets all fwhm to 25

    # crude test of every single pixel.
    for x in range(80):
        for y in range(60):
            if (50 <= x < 70) and (40 <= y < 50):
                if not np.array_equal(img.img[y][x], (1, 0, 1, 1)):
                    pytest.fail(f"rectangle not filled at {x} {y}")
            else:
                if not np.array_equal(img.img[y][x], (0, 0, 0, 0)):
                    pytest.fail(f"rectangle mistakenly filled at {x} {y}")
