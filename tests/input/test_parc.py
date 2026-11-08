import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *


def test_parc_load(globaldatadir):
    """Test loading a simple PARC file with a single item"""
    pcot.setup()
    doc = Document()

    assert doc.setInputPARC(0, "thisfiledoesntexist234234") == 'Cannot read file thisfiledoesntexist234234'
    assert doc.setInputPARC(0, str(globaldatadir/"parc/testimage.parc")) is None  # now try the right one

    node = doc.graph.create("input 0")
    doc.run()
    img = node.getOutput(0, Datum.IMG)
    assert img.channels == 2
    assert img.w == 32
    assert img.h == 32

    # check the sources.
    assert len(img.sources) == 2
    for sourceSet in img.sources:
        #  First, make sure each band has a source set of a single source
        assert len(sourceSet) == 1
        s = img.sources.sourceSets[0].getOnlyItem()
        # and that it's from input 0, and that it's attached to a Filter
        assert s.inputIdx == 0
        assert s.getFilter() is not None
    # now check the filter frequencies and names
    for ss, cwl, fwhm in zip(img.sources, (100, 200), (30, 30)):    # gen creates 30 fwhm for all filters
        s = ss.getOnlyItem()
        f = s.getFilter()
        assert f.cwl == cwl
        assert f.name == f"{cwl}"       # name is just the CWL
        assert f.position is None       # there is no position in the PARC file
        assert f.fwhm == fwhm           # the gen node sets all fwhm to 25

    # quick pixel checks

    assert np.allclose(img.img[22][16], (0.360292,0.896834))
    assert np.allclose(img.uncertainty[22][16], (1,1))
    assert img.dq[22][16][0] == 0
    assert img.dq[22][16][1] == 0

    assert np.allclose(img.img[9][18], (0.919903,0.817746))
    assert np.allclose(img.uncertainty[9][18], (0,1))
    assert img.dq[9][18][0] == dq.ERROR
    assert img.dq[9][18][1] == dq.ERROR


def test_parc_internal_roundtrip(globaldatadir):
    """Internal (undo/redo) serialisation of a document with a PARC input should keep the file and item,
    and an undo should keep the input's cached data rather than rereading it"""
    pcot.setup()
    doc = Document()
    assert doc.setInputPARC(0, str(globaldatadir/"parc/testimage.parc")) is None
    node = doc.graph.create("input 0")
    doc.run()
    orig = node.getOutput(0, Datum.IMG)

    # round trip into a new document - this has no cached data, so it reads the same item again
    d = doc.serialise(internal=True)
    doc2 = Document()
    doc2.deserialise(d, internal=True)
    method = doc2.inputMgr.inputs[0].getActive()
    assert method.fname == str(globaldatadir/"parc/testimage.parc")
    assert method.itemname == 'main'
    assert np.array_equal(method.get().get(Datum.IMG).img, orig.img)

    # undo in the same document - methods are deserialised into the existing objects,
    # so the cached data survives
    method = doc.inputMgr.inputs[0].getActive()
    cached = method.data
    doc.mark()
    doc.graph.create("expr")
    doc.undo()
    assert doc.inputMgr.inputs[0].getActive() is method
    assert method.data is cached
