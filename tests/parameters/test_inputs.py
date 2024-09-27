"""
Test modifications to inputs by parameter files
"""
import pcot
from fixtures import *
from pcot.datum import Datum
from pcot.document import Document
from pcot.parameters.inputs import processParameterFileForInputs
from pcot.parameters.parameterfile import ParameterFile


def test_no_items():
    pcot.setup()
    d = Document()
    f = ParameterFile().parse("")
    processParameterFileForInputs(d, f)


def test_rgb_input(globaldatadir):
    """Can we use a parameter file to modify a fresh document to load a couple of images as inputs?"""
    pcot.setup()

    # create a new document with no inputs (i.e. all inputs null)
    doc = Document()

    # create a parrameter file which will set a pair of RGB inputs
    test = f"""
    inputs.0.rgb.filename = {globaldatadir/'basn0g01.png'}  # black and white image
    inputs.1.rgb.filename = {globaldatadir/'basn2c16.png'}  # colour image
    """
    # process this directly
    f = ParameterFile().parse(test)
    processParameterFileForInputs(doc, f)

    # create the document with a couple of input nodes and run it
    # No need to create input 0, because one is created by default in new documents
    doc.graph.create("input 1")

    doc.run()
    # check the nodes - first node 0.
    img = doc.graph.getByDisplayName("input 0", True).getOutput(0, Datum.IMG)

    # check the basic stats - that it's the right image
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
        assert isinstance(s.band, str)      # not a filter, just a named band
        assert s.inputIdx == 0
        print(s.external)

    # now some more cursory tests on the second image
    img = doc.graph.getByDisplayName("input 1", True).getOutput(0, Datum.IMG)
    assert img.channels == 3
    assert img.w == 32
    assert img.h == 32
    assert np.array_equal(img.img[0][0], (1, 1, 0)) # top left yellow
    assert np.array_equal(img.img[31][31], (0, 0, 1)) # bottom right blue


def test_image_envi(envi_image_1, envi_image_2):
    """Test ENVI loading into two different inputs"""
    pcot.setup()

    # create a new document with no inputs (i.e. all inputs null)
    doc = Document()

    # create a parrameter file which will set a pair of RGB inputs
    test = f"""
    inputs.0.envi.filename = {envi_image_1}
    inputs.1.envi.filename = {envi_image_2}
    """
    # process this directly
    f = ParameterFile().parse(test)
    processParameterFileForInputs(doc, f)

    # create the document with a couple of input nodes and run it
    # No need to create input 0, because one is created by default in new documents
    doc.graph.create("input 1")
    doc.run()
    # check the nodes - first node 0.
    img = doc.graph.getByDisplayName("input 0", True).getOutput(0, Datum.IMG)

    # some very basic tests on the image (this is not a full test of ENVI load)
    assert img.channels == 4
    assert img.w == 80
    assert img.h == 60
    assert len(img.sources) == 4
    for ss, cwl in zip(img.sources, (800, 640, 550, 440)):
        f = ss.getOnlyItem().getFilter()
        assert f.cwl == cwl

    img = doc.graph.getByDisplayName("input 1", True).getOutput(0, Datum.IMG)

    # some very basic tests on the image (this is not a full test of ENVI load)
    assert img.channels == 4
    assert img.w == 80
    assert img.h == 60
    assert len(img.sources) == 4
    for ss, cwl in zip(img.sources, (1000, 2000, 3000, 4000)):
        f = ss.getOnlyItem().getFilter()
        assert f.cwl == cwl


def test_image_parc(globaldatadir):
    """Load a PARC image with uncertainty and DQ data"""
    pcot.setup()
    doc = Document()

    test = "inputs.0.parc.filename = " + str(globaldatadir / "parc/testimage.parc")
    f = ParameterFile().parse(test)
    processParameterFileForInputs(doc, f)

    doc.run()
    img = doc.graph.getByDisplayName("input 0", True).getOutput(0, Datum.IMG)

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


def test_multifile_simple(globaldatadir):
    """Load three PNGs with a simple filter pattern"""
    pcot.setup()
    doc = Document()
    test = f"""
    inputs.0.multifile.directory = {globaldatadir}/multi
    .filenames+ = FilterL02.png
    ..filenames+ = TestFilterL01image.png
    ..filenames+ = FilterR10.png
    ..filter_pattern = *Filter(?P<lens>L|R)(?P<n>[0-9][0-9]).*
    """

    f = ParameterFile().parse(test)
    f.dump()
    processParameterFileForInputs(doc, f)
    doc.run()
    img = doc.graph.getByDisplayName("input 0", True).getOutput(0, Datum.IMG)

    assert img.channels == 3

def test_foo():
    test = """
    foo.bar+ = 1
    .+ = 2
    """
    f = ParameterFile().parse(test)
    f.dump()