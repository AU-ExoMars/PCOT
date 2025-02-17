"""Test the direct input method"""
import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *
from pcot.value import Value


def test_direct_image(globaldatadir):
    """Use the special 'direct' input method to bring an ImageCube directly into the graph."""

    path = globaldatadir / 'basn2c16.png'
    inputimg = ImageCube.load(str(path), None, None)

    pcot.setup()
    doc = Document()

    assert doc.setInputDirectImage(0, inputimg) is None  # "load" an imagecube directly

    # create a document with just an input node in it, to bring that input into the document's graph
    node = doc.graph.create("input 0")
    # notify the document changed
    doc.run()
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

    assert img.sources[0].brief() == 'R'
    assert img.sources[1].brief() == 'G'
    assert img.sources[2].brief() == 'B'


    # check the input descriptions
    # assert doc.inputMgr.getInput(0).brief() == 'direct: 32x32x3'
    # ii = doc.inputMgr.getInput(0).long()  # this one has a UUID in the middle, so we have to just look at the ends
    # assert ii == 'direct: Image 32x32 array:(32, 32, 3) channels:3, 12288 bytes\nsrc: [R|G|B]'


def test_direct_scalar():
    """Test we can bring a numeric value into a graph with setInputDirect"""

    pcot.setup()
    doc = Document()
    v = Value(1, 2, dq.TEST)
    assert doc.setInputDirect(0, Datum(Datum.NUMBER, v, nullSource)) is None

    node = doc.graph.create("input 0")

    # process the input through an expr to check that connections work
    ee = doc.graph.create("expr")
    ee.connect(0, node, 0)
    ee.params.expr = "a+1"

    doc.run()
    out = ee.getOutputDatum(0)
    assert out.tp == Datum.NUMBER
    assert out.val.approxeq(Value(2, 2, dq.TEST))
