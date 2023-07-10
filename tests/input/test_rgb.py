"""RGB input tests"""
import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *


def test_rgb_load(globaldatadir):
    """Test we can load an RGB file (a PNG)"""
    pcot.setup()
    doc = Document()
    # having created a document, set an input. Try one that doesn't exist first.
    assert doc.setInputRGB(0, "thisfiledoesntexist234234") == 'Cannot read file thisfiledoesntexist234234'
    assert doc.setInputRGB(0, str(globaldatadir / "basn0g01.png")) is None  # now try the right one
    # create a document with just an input node in it, to bring that input into the document's graph
    node = doc.graph.create("input 0")
    # notify the document changed
    doc.changed()
    # and get the output of the node, which should be the image loaded from the ENVI
    img = node.getOutput(0, Datum.IMG)
    # check the basic stats
    assert img.channels == 3
    assert img.w == 32
    assert img.h == 32
    assert np.array_equal(img.img[0][0], (1, 1, 1))
    assert np.array_equal(img.img[31][31], (0, 0, 0))

    assert len(img.sources) == 3
    for sourceSet, colname in zip(img.sources, ['R', 'G', 'B']):
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = sourceSet.getOnlyItem()
        # and that it's from input 0, and that it's attached to a name, not a filter
        assert s.inputIdx == 0
        assert isinstance(s.filterOrName, str)
        assert s.filterOrName == colname
