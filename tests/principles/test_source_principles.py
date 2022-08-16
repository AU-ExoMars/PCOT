import pcot
from basic.test_sources import SimpleTestSource
from fixtures import *
from pcot.datum import Datum
from pcot.document import Document


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
    # TODO - load ENVI file with bands. Convert to GS. Check sources.
    assert envi_img.channels == 4
    # I'm going to use the expr "grey" function here. It takes Datum arrays. The second
    # argument specifies whether we are using opencv greyscaling (must be 3 channels).
    # Note that we have to specify a source for the numeric value (it's ignored by the function, which
    # might seem odd given the Rules, but it only determines a mode and almost never comes from outside).
    # Since this is a slightly edge behaviour I'll test for it.
    nsource = SimpleTestSource("numbersource")

    from pcot.expressions.eval import funcGrey
    d = funcGrey([Datum(Datum.IMG, envi_img)], [Datum(Datum.NUMBER, 0, nsource)])
    img = d.get(Datum.IMG)
    assert img.channels == 1        # single channel
    assert len(img.sources) == 1    # and therefore a single sourceset

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
