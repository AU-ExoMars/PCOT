import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *
from pcot.filters import Filter
from pcot.sources import SourceSet


def test_envi_1(envi_image_1):
    pcot.setup()
    doc = Document()
    # having created a document, set an input. Try one that doesn't exist first.
    assert doc.setInputENVI(0, "thisfiledoesntexist234234") == 'Cannot read file thisfiledoesntexist234234'
    assert doc.setInputENVI(0, envi_image_1) is None  # now try the right one

    # create a document with just an input node in it, to bring that input into the document's graph
    node = doc.graph.create("input 0")
    # notify the document changed
    doc.changed()
    # and get the output of the node, which should be the image loaded from the ENVI
    img = node.getOutput(0, Datum.IMG)
    # check the basic stats
    assert img.channels == 4
    assert img.w == 80
    assert img.h == 60

    # check the sources.
    for ss in img.sources.sourceSets:
        #  First, make sure each band has a source set of a single source
        assert len(ss.sourceSet) == 1
        s, = img.sources.sourceSets[0].sourceSet
        # and that it's from input 0, and that it's attached to a Filter
        assert s.inputIdx == 0
        assert isinstance(s.filterOrName, Filter)
    # now check the filter frequencies and names
    for i, cwl in enumerate((800, 640, 550, 440)):
        s, = img.sources.sourceSets[i].sourceSet
        f = s.filterOrName
        assert f.cwl == cwl
        assert f.name == f"L{i+1}_{cwl}"        # gen_envi generates names in the form Ln_cwl, n starts at 1
        assert f.position == f"L{i+1}_{cwl}"
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
