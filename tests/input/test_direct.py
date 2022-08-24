import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *
from pcot.filters import Filter


def test_direct(globaldatadir):
    """Use the special 'direct' input method to bring an ImageCube directly into the graph."""

    path = globaldatadir / 'basn2c16.png'
    inputimg = ImageCube.load(str(path), None, None)

    pcot.setup()
    doc = Document()

    assert doc.setInputDirect(0, inputimg) is None  # "load" an imagecube directly

    # create a document with just an input node in it, to bring that input into the document's graph
    node = doc.graph.create("input 0")
    # notify the document changed
    doc.changed()
    # and get the output of the node, which should be the image loaded from the ENVI
    img = node.getOutput(0, Datum.IMG)
    # check the basic stats
    assert img.channels == 3
    assert img.h == 32
    assert img.w == 32

    assert np.array_equal(img.img[0][0], [1, 1, 0])
    assert np.array_equal(img.img[img.h - 1][img.w - 1], [0, 0, 1])

    # check the sources.
    assert len(img.sources) == 3
    for sourceSet in img.sources:
        #  Each sourceset is empty
        assert len(sourceSet) == 0
