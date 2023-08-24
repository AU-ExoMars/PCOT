"""Test the basic principles behind how sources are propagated
through the graph"""

import pcot
from basic.test_sources import SimpleTestSource
from fixtures import *
from pcot.datum import Datum
from pcot.document import Document
from pcot.sources import SourceSet, InputSource
from pcot.value import Value
from pcot.xform import XFormException


@pytest.fixture
def envi_img(envi_image_1):
    """Fixture to load ENVI image into a graph"""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None

    node = doc.graph.create("input 0")
    doc.changed()
    img = node.getOutput(0, Datum.IMG)
    assert img is not None
    return img


def test_envi_sources(envi_img: ImageCube):
    """make sure ENVI sources work as expected"""
    assert envi_img.channels == 4
    assert isinstance(envi_img.sources, MultiBandSource)

    # here we're using the convenience dunder methods a lot.
    assert len(envi_img.sources) == 4
    for sourceset, freq in zip(envi_img.sources, (800, 640, 550, 440)):
        assert sourceset.getOnlyItem().getFilter().cwl == freq


def test_greyscale_sources(envi_img: ImageCube):
    """Make sure conversion to greyscale using the grey() function works with regard to sources - this will
    stand in for certain aspects of the sources principles."""
    assert envi_img.channels == 4
    # I'm going to use the expr "grey" function here. It takes Datum arrays. The second
    # argument specifies whether we are using opencv greyscaling (must be 3 channels).
    # Note that we have to specify a source for the numeric value (it's ignored by the function, which
    # might seem odd given the Rules, but it only determines a mode and almost never comes from outside).
    # Since this is a slightly edge behaviour I'll test for it.
    nsource = SimpleTestSource("numbersource")  # numbers need explicit sources, so I'll fake one up

    from pcot.expressions.builtins import funcGrey
    d = funcGrey([Datum(Datum.IMG, envi_img)], [Datum(Datum.NUMBER, Value(0, 0), nsource)])
    img = d.get(Datum.IMG)
    assert img.channels == 1  # single channel
    assert len(img.sources) == 1  # and therefore a single sourceset

    sources = img.sources[0]
    assert len(sources) == 5  # four channels plus the number determining type

    # separate into sources which have filters (those from images) and others
    filts = [x for x in sources if x.getFilter() is not None]
    nonfilts = [x for x in sources if x.getFilter() is None]
    assert len(nonfilts) == 1
    assert len(filts) == 4

    # make sure that the number source got there
    assert nonfilts[0].brief() == 'numbersource'
    # and get the filter freqs to make sure they are correct
    freqs = set(x.getFilter().cwl for x in sources if x.getFilter() is not None)
    assert {800, 640, 550, 440} == freqs


def test_greyscale_sources_expr(envi_image_1):
    """Make sure conversion to greyscale using the grey() function works with regard to sources - this will
    stand in for certain aspects of the sources principles. As test_greyscale_sources(), but uses an actual
    expr node."""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None

    inputNode = doc.graph.create("input 0")
    exprNode = doc.graph.create("expr")
    exprNode.expr = "grey(a,0)"
    # connect input 0 on self to output 0 in the input node
    exprNode.connect(0, inputNode, 0)

    doc.changed()
    img = exprNode.getOutput(0, Datum.IMG)
    assert img is not None

    assert img.channels == 1  # single channel
    assert len(img.sources) == 1  # and therefore a single sourceset

    sources = img.sources[0]
    # four channels - the number determining the type of greyscaling will be
    # a null source that gets filtered out.
    assert len(sources) == 4

    # separate into sources which have filters (those from images) and others
    filts = [x for x in sources if x.getFilter() is not None]
    nonfilts = [x for x in sources if x.getFilter() is None]
    assert len(filts) == 4

    assert len(nonfilts) == 0   # might seem an odd test, is a historical artifact (null sources now filtered out)
    # make sure that the number source is the null source (commented out, see previous line)
    # assert nonfilts[0] == nullSource

    # and get the filter freqs to make sure they are correct
    freqs = set(x.getFilter().cwl for x in sources if x.getFilter() is not None)
    assert {800, 640, 550, 440} == freqs


def test_extract_sources(envi_image_1):
    """Make sure that an expression of the form a$n works as expected with sources, this time
    using an actual expr node"""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None

    inputNode = doc.graph.create("input 0")
    exprNode = doc.graph.create("expr")
    exprNode.expr = "a$640"
    # connect input 0 on self to output 0 in the input node
    exprNode.connect(0, inputNode, 0)

    doc.changed()
    img = exprNode.getOutput(0, Datum.IMG)
    assert img is not None
    assert len(img.sources) == 1
    sourceset = img.sources[0]
    assert len(sourceset) == 1
    source = sourceset.getOnlyItem()
    assert source.getFilter().cwl == 640


def test_extract_by_band():
    """Test that we can extract by band, and that out-of-range bands give an error. Testing of the DQ
    and uncertainty is done in a graph setting by graphs/extractbyband.pcot"""

    pcot.setup()
    doc = Document()
    img = genrgb(50, 50, 0.1, 0.2, 0.3, doc=doc, inpidx=0)
    assert doc.setInputDirect(0, img) is None
    inp = doc.graph.create("input 0")
    expr = doc.graph.create("expr")
    expr.expr = "a$_0"
    expr.connect(0,inp,0)
    doc.changed()

    img = expr.getOutput(0, Datum.IMG)
    assert img is not None
    assert np.allclose(img.img[0][0], 0.1)

    expr.expr = "a$_4"
    doc.changed()
    img = expr.getOutput(0, Datum.IMG)
    assert img is None
    assert isinstance(expr.error, XFormException)
    assert expr.error.message == "unable to get this wavelength from an image: [DATUM-ident, value _4]"


def test_binop_2images(envi_image_1, envi_image_2):
    """Make sure that sources work with two images combined in an expr node."""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None
    assert doc.setInputENVI(1, envi_image_2) is None

    inputNode1 = doc.graph.create("input 0")
    inputNode2 = doc.graph.create("input 1")
    exprNode = doc.graph.create("expr")
    exprNode.expr = "a+b"
    exprNode.connect(0, inputNode1, 0)  # expr:0 <- input1:0
    exprNode.connect(1, inputNode2, 0)  # expr:1 <- input2:0

    doc.changed()
    img = exprNode.getOutput(0, Datum.IMG)
    assert img is not None
    assert isinstance(img.sources, MultiBandSource)
    assert len(img.sources) == 4  # 4-band image
    # here we test each source - it should have a pair of frequencies, one of which comes from the band in input1,
    # the other comes from the band in input2.
    for freqPair, channelSourceSet in zip(((800, 1000), (640, 2000), (550, 3000), (440, 4000)), img.sources):
        assert len(channelSourceSet) == 2
        a, b = freqPair
        # we do this because the source set is a set and we can't guarantee the order, so we get
        # the frequencies and sort them. Relies on input 0's freqs all being below input 1's.
        channelFreqs = sorted([x.getFilter().cwl for x in channelSourceSet])
        assert channelFreqs[0] == a
        assert channelFreqs[1] == b


def test_binop_number_and_number(envi_image_1, envi_image_2):
    """Make sure that sources work with two images combined in an expr node, but where both images are converted
    to numbers (using mean). We should get a single source set made up of all the sources."""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None
    assert doc.setInputENVI(1, envi_image_2) is None

    inputNode1 = doc.graph.create("input 0")
    inputNode2 = doc.graph.create("input 1")
    exprNode = doc.graph.create("expr")
    exprNode.expr = "mean(a)*mean(b)"  # multiply mean of image A by the mean of image B
    exprNode.connect(0, inputNode1, 0)  # expr:0 <- input1:0
    exprNode.connect(1, inputNode2, 0)  # expr:1 <- input2:0

    doc.changed()
    datum = exprNode.getOutputDatum(0)  # don't actually care what the answer is - we just want to check the sources.
    assert isinstance(datum.sources, SourceSet)
    assert len(datum.sources) == 8  # 2 images with 4 bands

    # split into sources which came from each input - each should have 4 members
    fromImage1 = [x for x in datum.sources if x.inputIdx == 0]
    fromImage2 = [x for x in datum.sources if x.inputIdx == 1]

    # and check the sets have the right frequencies
    assert set([x.getFilter().cwl for x in fromImage1]) == {800, 640, 550, 440}
    assert set([x.getFilter().cwl for x in fromImage2]) == {1000, 2000, 3000, 4000}


def test_binop_image_and_number(envi_image_1, envi_image_2):
    """Make sure that sources work with two images combined in an expr node, but where both images are converted
    to numbers (using mean). We should get a single source set made up of all the sources."""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None
    assert doc.setInputENVI(1, envi_image_2) is None

    inputNode1 = doc.graph.create("input 0")
    inputNode2 = doc.graph.create("input 1")
    exprNode = doc.graph.create("expr")
    exprNode.expr = "a*mean(b)"  # multiply image A by the mean of image B
    exprNode.connect(0, inputNode1, 0)  # expr:0 <- input1:0
    exprNode.connect(1, inputNode2, 0)  # expr:1 <- input2:0

    doc.changed()

    img = exprNode.getOutput(0, Datum.IMG)
    assert img is not None

    assert isinstance(img.sources, MultiBandSource)
    assert len(img.sources) == 4  # 4 bands in the output

    for freq, channelSourceSet in zip((800, 640, 550, 440), img.sources):
        # each channel's sources should be the relevant channel of A plus all the channels of B.
        assert len(channelSourceSet) == 5
        # split into sources which came from each input - each should have 4 members
        fromImage1 = [x for x in channelSourceSet if x.inputIdx == 0]
        fromImage2 = [x for x in channelSourceSet if x.inputIdx == 1]
        assert len(fromImage1) == 1
        assert len(fromImage2) == 4
        assert fromImage1[0].getFilter().cwl == freq
        assert set([x.getFilter().cwl for x in fromImage2]) == {1000, 2000, 3000, 4000}


def test_binop_image_and_number2(envi_image_1, envi_image_2):
    """Similar to test_binop_image_and_number, but we do it the other way around and use a different binop"""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None
    assert doc.setInputENVI(1, envi_image_2) is None

    inputNode1 = doc.graph.create("input 0")
    inputNode2 = doc.graph.create("input 1")
    exprNode = doc.graph.create("expr")
    exprNode.expr = "mean(a)-b"  # subtract image B from the mean of image A
    exprNode.connect(0, inputNode1, 0)  # expr:0 <- input1:0
    exprNode.connect(1, inputNode2, 0)  # expr:1 <- input2:0

    doc.changed()

    img = exprNode.getOutput(0, Datum.IMG)
    assert img is not None

    assert isinstance(img.sources, MultiBandSource)
    assert len(img.sources) == 4  # 4 bands in the output

    for freq, channelSourceSet in zip((1000, 2000, 3000, 4000), img.sources):
        # each channel's sources should be the relevant channel of A plus all the channels of B.
        assert len(channelSourceSet) == 5
        # split into sources which came from each input - each should have 4 members
        fromImage1 = [x for x in channelSourceSet if x.inputIdx == 0]
        fromImage2 = [x for x in channelSourceSet if x.inputIdx == 1]
        assert len(fromImage1) == 4
        assert len(fromImage2) == 1
        assert fromImage2[0].getFilter().cwl == freq
        assert set([x.getFilter().cwl for x in fromImage1]) == {800, 640, 550, 440}


def test_binop_image_and_number_literal(envi_image_1, envi_image_2):
    """Similar to test_binop_image_and_number, but we do it the other way around and use a different binop
    AND the number is a literal."""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None

    inputNode1 = doc.graph.create("input 0")
    exprNode = doc.graph.create("expr")
    exprNode.expr = "a-20"  # subtract literal 20 from the mean of image A
    exprNode.connect(0, inputNode1, 0)  # expr:0 <- input1:0

    doc.changed()

    img = exprNode.getOutput(0, Datum.IMG)
    assert img is not None

    assert isinstance(img.sources, MultiBandSource)
    assert len(img.sources) == 4  # 4 bands in the output

    for freq, channelSourceSet in zip((800, 640, 550, 440), img.sources):
        # each channel's sources should be the relevant channel of A and the null source,
        # but the null source gets filtered out
        assert len(channelSourceSet) == 1
        fromImage = [x for x in channelSourceSet if isinstance(x, InputSource)]
        fromConst = [x for x in channelSourceSet if x == nullSource]
        assert len(fromImage) == 1
        assert len(fromConst) == 0
        assert fromImage[0].getFilter().cwl == freq


def test_unop_image(envi_image_1):
    """Test that sources are propagated correctly through a unary op"""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None

    inputNode1 = doc.graph.create("input 0")
    exprNode = doc.graph.create("expr")
    exprNode.expr = "-a"  # negate image
    exprNode.connect(0, inputNode1, 0)  # expr:0 <- input1:0

    doc.changed()

    img = exprNode.getOutput(0, Datum.IMG)
    assert img is not None
    assert isinstance(img.sources, MultiBandSource)
    assert len(img.sources) == 4  # 4 bands in the output

    for freq, channelSourceSet in zip((800, 640, 550, 440), img.sources):
        assert len(channelSourceSet) == 1
        assert channelSourceSet.getOnlyItem().getFilter().cwl == freq


def test_unop_number_from_image(envi_image_1):
    """Turn image into number, perform unop on number. Should produce a single source set of
    all channels in the image."""
    pcot.setup()
    doc = Document()
    assert doc.setInputENVI(0, envi_image_1) is None

    inputNode1 = doc.graph.create("input 0")
    exprNode = doc.graph.create("expr")
    exprNode.expr = "-mean(a)"  # negate image mean
    exprNode.connect(0, inputNode1, 0)  # expr:0 <- input1:0

    doc.changed()

    datum = exprNode.getOutputDatum(0)  # don't actually care what the answer is - we just want to check the sources.
    assert isinstance(datum.sources, SourceSet)

    assert len(datum.sources) == 4
    assert set([x.getFilter().cwl for x in datum.sources]) == {800, 640, 550, 440}
