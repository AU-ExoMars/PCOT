"""
This file tests the fundamental functionality of the spectrum system. If you
want to look at tests for the spectrum XForm, check the graphs directory.
"""
import json
import os

import pytest

import pcot
from pcot.datum import Datum
from pcot.document import Document
from pcot.rois import ROICircle, ROIRect, ROI
from pcot.cameras.filters import Filter
from pcot.utils.spectrum import Spectrum, SpectrumSet, NameResolver, spectrumFromImage, coalesceROIs
from pcot.utils.spectrumdata import SpectrumValue
from pcot.value import Value
from fixtures import globaldatadir


def create_test_image1():
    """we're going to use a "standard image" made using the "gen" xform. To do this, I'm going to
    spin up PCOT and create a document with a gen node in it. If you want to look at this image,
    open the spectrum.pcot file in the test graph directory and look at the "gen check 2" node.

    This image has constant uncertainty (0).
    """
    pcot.setup()
    doc = Document()

    node = doc.graph.create("gen")
    node.params.imgwidth, node.params.imgheight = 256, 256

    # some cleverness here because each TaggedDict we create inside the chans TaggedList is ordered.
    node.params.chans.append_default().set(2, 10, 100, "gradient-x")
    node.params.chans.append_default().set(3, 20, 200, "gradient-y")
    node.params.chans.append_default().set(25, 0, 300, "checkx")

    doc.run()
    img = node.getOutput(0, Datum.IMG)
    assert img.channels == 3  # just to be sure
    return img


def get_dot(img, x, y, r=3):
    """get the spectrum of a small part of the image"""
    # first add an ROI to the image
    roi = ROICircle(x, y, r, label="testroi")
    img.rois.append(roi)
    return spectrumFromImage(img, roi)


def generate_test_data():
    # Create two images, both 256x256. We use the gen node for this.
    img1 = create_test_image1()
    img2 = create_test_image1()
    # add some ROIs to each image.
    # For img1 we'll add two rects with the same name and a circle.
    img1.rois.append(ROIRect(rect=(10, 10, 20, 20), label="1"))
    img1.rois.append(ROIRect(rect=(30, 30, 40, 40), label="1"))
    img1.rois.append(ROICircle(50, 50, 10, label="2"))
    # For img2 we'll do the same, but with three rects and two circles.
    img2.rois.append(ROIRect(rect=(0, 0, 30, 50), label="1"))
    img2.rois.append(ROIRect(rect=(100, 100, 20, 20), label="1"))
    img2.rois.append(ROIRect(rect=(100, 60, 20, 20), label="1"))
    img2.rois.append(ROICircle(60, 60, 20, label="2"))
    img2.rois.append(ROICircle(80, 80, 20, label="2"))

    return img1, img2


def test_coalesce():
    """Test that ROIs with the same name are combined into one ROI, but not across images"""

    img1, img2 = generate_test_data()

    # now we'll build the dict that coalesce (and SpectrumSet) works on
    d = {
        'img1': img1,
        'img2': img2
    }
    # and coalesce
    coalesceROIs(d)
    # extract the images from the dict
    img1 = d['img1']
    img2 = d['img2']

    # now we check to see what ROIs are in the images. There should be two ROIs, where one is a union
    # of the two rects and the other is the circle.
    assert len(img1.rois) == 2
    assert len(img2.rois) == 2

    # check that we have 1 ROI which is a union of the two rects
    x = [r for r in img1.rois if r.label == "1"]
    assert len(x) == 1
    x = x[0]  # extract the ROI from the list
    assert type(x) == ROI  # assert it's an ROI and not a subclass of ROI
    # check that the union ROI has the right bounds
    bb = x.bb()
    assert bb[0] == 10
    assert bb[1] == 10
    assert bb[2] == 60
    assert bb[3] == 60
    # and just check the corners
    assert (10, 10) in x
    assert (10, 69) not in x
    assert (69, 10) not in x
    assert (69, 69) in x
    assert (70, 70) not in x
    assert (9, 9) not in x
    # check the circle
    x = [r for r in img1.rois if r.label == "2"]
    assert len(x) == 1
    x = x[0]
    assert type(x) == ROICircle
    assert x.x == 50
    assert x.y == 50
    assert x.r == 10

    # do some basic checks on image 2
    x = [r for r in img2.rois if r.label == "1"]
    assert len(x) == 1
    x = x[0]
    assert type(x) == ROI
    bb = x.bb()
    # check dimensions and some points
    assert bb[0] == 0
    assert bb[1] == 0
    assert bb[2] == 120
    assert bb[3] == 120
    assert (0, 0) in x
    assert (29, 49) in x
    assert (0, 49) in x
    assert (29, 0) in x
    assert (30, 50) not in x
    assert (100, 100) in x
    assert (119, 119) in x
    assert (120, 120) not in x
    assert (100, 60) in x
    assert (120, 80) not in x
    # get the circles
    x = [r for r in img2.rois if r.label == "2"]
    assert len(x) == 1  # which should have been coalesced
    x = x[0]
    assert type(x) == ROI
    # and check the dimensions and some points
    bb = x.bb()
    assert bb[0] == 40
    assert bb[1] == 40
    assert bb[2] == 61
    assert bb[3] == 61
    assert (40, 40) not in x
    assert (40, 60) in x
    assert (100, 80) in x
    assert (80, 100) in x
    assert (98, 98) not in x


def test_name_resolution():
    """Multiple ROIs with the same name in different images should be disambiguated"""
    # Create two images, both 256x256. We use the gen node for this.
    img1 = create_test_image1()
    img2 = create_test_image1()
    # add some ROIs to each image.
    r1_1a = ROIRect(rect=(10, 10, 20, 20), label="1")
    r1_1b = ROIRect(rect=(30, 30, 40, 40), label="1")
    r1_2 = ROICircle(50, 50, 10, label="2")
    img1.rois = [r1_1a, r1_1b, r1_2]

    r2_1a = ROIRect(rect=(0, 0, 30, 50), label="1")
    r2_1b = ROICircle(60, 60, 20, label="1")
    r2_2a = ROIRect(rect=(100, 60, 20, 20), label="2")
    r2_2b = ROIRect(rect=(120, 80, 20, 20), label="2")
    r2_3 = ROIRect(rect=(140, 100, 20, 20), label="3")
    img2.rois = [r2_1a, r2_1b, r2_2a, r2_2b, r2_3]

    # build the dict and coalesce
    d = {'img1': img1, 'img2': img2}
    coalesceROIs(d)
    # extract the images from the dict
    img1 = d['img1']
    img2 = d['img2']

    # do basic checks
    assert len(img1.rois) == 2
    assert len(img2.rois) == 3

    # get the "new" ROIs (some will be coalesced)
    r1_1 = [r for r in img1.rois if r.label == "1"][0]
    r1_2 = [r for r in img1.rois if r.label == "2"][0]
    r2_1 = [r for r in img2.rois if r.label == "1"][0]
    r2_2 = [r for r in img2.rois if r.label == "2"][0]
    r2_3 = [r for r in img2.rois if r.label == "3"][0]

    # now do test the resolution
    resolver = NameResolver(d)
    assert "img1:1" == resolver.resolve("img1", r1_1)
    assert "img1:2" == resolver.resolve("img1", r1_2)  # will be coalesced, it exists in img2
    assert "img2:1" == resolver.resolve("img2", r2_1)
    assert "img2:2" == resolver.resolve("img2", r2_2)
    assert "3" == resolver.resolve("img2", r2_3)  # will not be coalesced, it does not exist in img1


def test_spectrum():
    img = create_test_image1()
    assert img.channels == 3

    s = get_dot(img, 187, 211)
    # check we can get filters and values
    # by wavelength
    assert s.get(100).v == Value(1, 0, 0)
    assert s.get(200).v == Value(1, 0, 0)
    assert s.get(300).v == Value(1, 1, 0)

    # just check non-existent filters return None
    assert s.get("fish") is None
    assert s.get(400) is None

    # try another dot with a straightforward variance
    s = get_dot(img, 62, 110)
    assert s.get(100).v == Value(0, 0, 0)
    assert s.get(200).v == Value(0.5, 0, 0)
    assert s.get(300).v == Value(0, 0, 0)
    # test sample/pixel counts work
    assert s.get(100).samples == 29
    assert s.get(200).samples == 29
    assert s.get(300).samples == 29

    # and now one that straddes a boundary between regions
    # in a filter, but with there is zero variance within the pixels
    # (so the nominal values vary, but the uncertainty values are all zero).
    # Here, the 200 filter is half 0.5 and half 0.0. The data will have the form
    # [[--, --, 0.0, --, --],
    #  [--, 0.0, 0.0, 0.0, --],
    #  [0.0, 0.0, 0.0, 0.0, 0.0],
    #  [--, 0.5, 0.5, 0.5, --],
    #  [--, --, 0.5, --, --]]
    # so the mean will be 0.15384615384615385
    # and the stddev will be 0.23076923076923078
    s = get_dot(img, 62, 84, 2)  # radius of 2
    assert s.get(100).v == Value(0, 0, 0)
    assert s.get(200).v == Value(0.15384615384615385, 0.23076923076923078, 0)
    assert s.get(300).v == Value(1, 1, 0)
    assert s.get(100).samples == 13  # test the pixel count works!

    # check we can get by filter name (the gen node names filters after their wavelengths)
    assert s.get("100").v == Value(0, 0, 0)
    assert s.get("200").v == Value(0.15384615384615385, 0.23076923076923078, 0)
    assert s.get("300").v == Value(1, 1, 0)
    # the spectrum takes its colour from the ROI
    assert s.colour == tuple(img.rois[-1].colour)


def create_test_image2():
    """Another test image - this uses the "gen check 3" node and its descendants in the same
    graph as the previous test image. This one has a rather more complex uncertainty pattern."""
    pcot.setup()
    doc = Document()

    # generates the nominal values
    gen = doc.graph.create("gen")
    gen.params.imgwidth, gen.params.imgheight = 256, 256
    gen.params.chans.append_default().set(2, 10, 100, "gradient-x")
    gen.params.chans.append_default().set(2, 20, 200, "gradient-y")

    # we want the 200 channel to be multiplied
    mult200 = doc.graph.create("expr")
    mult200.params.expr = "merge(a$100,a$200*0.5)"
    mult200.connect(0, gen, 0)

    # offset to get uncertainties
    offset = doc.graph.create("offset")
    offset.params.x, offset.params.y = 1, 1
    offset.connect(0, mult200, 0)
    # combine the two with an expression
    expr = doc.graph.create("expr")
    expr.params.expr = "v(a*0.5+0.3,b*0.2+0.1)"
    expr.connect(0, mult200, 0)
    expr.connect(1, offset, 0)

    doc.run()
    img = expr.getOutput(0, Datum.IMG)
    assert img.channels == 2  # just to be sure
    return img


def test_spectrum_pooling():
    # and now one that straddes a boundary between regions of both different nominal values
    # and different uncertainties. This uses a different test image which uses an offset node
    # to create a more complex nominal/uncertainty pattern. This lets us test that pooling
    # of uncertainties works correctly.

    img = create_test_image2()

    # Channel 0 (wavelength 100):
    # The pattern here in nominal values is:
    # [[--, --, 0.8, --, --],
    #  [--, 0.3, 0.8, 0.8, --],
    #  [0.3, 0.3, 0.8, 0.8, 0.8],
    #  [--, 0.3, 0.8, 0.8, --],
    #  [--, --, 0.8, --, --]],
    # and in uncertainties is:
    # [[--, --, 0.1, --, --],
    #  [--, 0.1, 0.1, 0.3, --],
    #  [0.1, 0.1, 0.1, 0.3, 0.3],
    #  [--, 0.1, 0.1, 0.3, --],
    #  [--, --, 0.1, --, --]],
    # so the mean will be 0.6461538461538463.
    #
    # The raw variance of the nominal values is 0.053254437869822494
    # The mean of the variances in the uncertainty channel is
    # obtained by squaring the uncertainties (which are stddevs) and taking the mean:
    # 0.03461538461538462
    # Therefore the variance of the means plus the mean of the variances is
    # 0.053254437869822494 + 0.03461538461538462 = 0.087869822494
    # which gives a stddev of 0.2964284441230415

    s = get_dot(img, 128, 128, 2)
    assert s.get(100).v == Value(0.6461538461538463, 0.2964284441230415, 0)

    # Channel 1 (wavelength 200):
    # Nominal values:
    # [[--, --, 0.3, --, --],
    #  [--, 0.3, 0.3, 0.3, --],
    #  [0.55, 0.55, 0.55, 0.55, 0.55],
    #  [--, 0.55, 0.55, 0.55, --],
    #  [--, --, 0.55, --, --]],
    # Uncertainties:
    # [[--, --, 0.1, --, --],
    #  [--, 0.1, 0.1, 0.1, --],
    #  [0.1, 0.1, 0.1, 0.1, 0.1],
    #  [--, 0.2, 0.2, 0.2, --],
    #  [--, --, 0.2, --, --]],
    # so the mean will be 0.4730769230769231
    # Raw variance of means: 0.013313609467455627
    # Mean of individual variances: 0.019230769230769235
    # Sum is : 0.032544378698224866
    # So root of sum is 0.18040060614705503
    #
    # Having to use approx equality here because of floating point errors!

    assert s.get(200).v.approxeq(Value(0.4730769230769231, 0.18040060614705503, 0))


def test_spectrum_table(globaldatadir):
    """This test uses the graph for spectrum.pcot. It collects images with ROIs from the graph,
    constructs SpectrumSets directly, and compares the results (when converted to strings) with
    the expected results from the graph."""

    pcot.setup()

    # we are reusing the graph here to generate the images and ROIs
    doc = Document(globaldatadir / "../graphs/spectrum.pcot")
    doc.run()  # force the graph to run

    # get the gen and multidot node outputs
    gen1img = doc.graph.getByDisplayName("gen 1", single=True).getOutput(0, Datum.IMG)
    gen2img = doc.graph.getByDisplayName("gen 2", single=True).getOutput(0, Datum.IMG)
    md1img = doc.graph.getByDisplayName("multidot 1", single=True).getOutput(0, Datum.IMG)
    md2img = doc.graph.getByDisplayName("multidot 2", single=True).getOutput(0, Datum.IMG)
    md3img = doc.graph.getByDisplayName("multidot 3", single=True).getOutput(0, Datum.IMG)

    # get desired results; strip and convert crlf to lf. This deals with platform differences.
    # This is really ugly because we need to rummage around inside the node!

    res1 = doc.graph.getByDisplayName("stringtest 1", single=True).params.string.strip().replace('\r\n', '\n')

    # create the spectrum sets and tables for the gen1/md1 set (look at the graph, you can see that
    # gen1 and md1 connect to inputs 0 and 4 on the spectrum node).
    ss1 = SpectrumSet.fromImages({"in0": gen1img, "in4": md1img})
    t = str(ss1).strip().replace('\r\n', '\n')
    assert t == res1

    # same with md2
    res2 = doc.graph.getByDisplayName("stringtest 2", single=True).params.string.strip().replace('\r\n', '\n')
    ss2 = SpectrumSet.fromImages({"in0": md2img})
    t = str(ss2).strip().replace('\r\n', '\n')
    assert t == res2

    # and finally the complex test with md3
    res3 = doc.graph.getByDisplayName("stringtest 3", single=True).params.string.strip().replace('\r\n', '\n')
    ss3 = SpectrumSet.fromImages({
        "in0": gen1img,
        "in1": md1img,
        "in2": md2img,
        "in3": gen2img,
        "in4": md3img
    })
    t = str(ss3).strip().replace('\r\n', '\n')
    assert t == res3


def test_spectrum_data():
    img1, img2 = generate_test_data()

    d = {
        'img1': img1,
        'img2': img2
    }
    ss = SpectrumSet.fromImages(d)

    # SpectrumSet acts as a dict of ROI name (or img:ROI) to Spectrum
    s = ss["img1:1"]
    assert isinstance(s, Spectrum)

    def check(s):
        # Spectrum contains a map of Filter to data but has accessors for that. First, let's check
        # the wavelengths are right, and the filter data - gen nodes always set fwhm = 30 in their "fake" filters
        assert [(f.name, f.cwl, f.fwhm) for f in s.filters()] == [('100', 100, 30), ('200', 200, 30), ('300', 300, 30)]
        # now the actual values
        assert s.get(100).v == Value(0, 0, 0)
        assert s.get(200).v == Value(0, 0, 0)
        assert s.get(300).v.approxeq(Value(0.475, 0.8511, 0))
        # all filters were measured over the same coalesced ROI
        for f in s.filters():
            assert s.values[f].samples == 2000

    check(s)

    # round trip test, through JSON
    data = json.dumps(ss.serialise())
    data = json.loads(data)
    ss2 = SpectrumSet.deserialise(data)

    assert list(ss2.keys()) == list(ss.keys())
    check(ss2["img1:1"])
    # colours survive the round trip
    for name in ss.keys():
        assert ss2[name].colour == ss[name].colour


def test_tabular_provider():
    img1, img2 = generate_test_data()

    d = {
        'img1': img1,
        'img2': img2
    }
    ss = SpectrumSet.fromImages(d)

    # get a tabular provider
    t = ss.tabularProvider()
    # can we get the headers and are they correct?
    hdrs = t.getHeaders()
    assert hdrs == ['name', 'm100', 's100', 'n100', 'm200', 's200', 'n200', 'm300', 's300', 'n300']
    # can we iterate over the data?
    for x in t:
        # are the right keys - and only those - there?
        assert set(x.keys()) == set(hdrs)
        # I'll leave checking the actual data for now. That can be done in a graph,
        # converting to strings (as we do right now). But I will show what it
        # roughly looks like
        roiname = x['name']
        Value(x['m100'],x['s100'])


def S(filters, values, colour=None):
    """Build a spectrum by hand from a dict of filter name to (cwl, fwhm) and a dict of
    filter name to SpectrumValue"""
    fs = {name: Filter(cwl, fwhm, name=name) for name, (cwl, fwhm) in filters.items()}
    return Spectrum({fs[name]: v for name, v in values.items()}, colour)


def test_tabular_provider_awkward_spectra():
    """Spectra built by hand to hit the awkward cases: float wavelengths (including a fractional one),
    and a spectrum which doesn't have a filter at every wavelength the others do."""
    a = S({'F1': (440.0, 25), 'F2': (438.5, 25)},
          {'F1': SpectrumValue(Value(0.25, 0.01, 0), 10),
           'F2': SpectrumValue(Value(0.5, 0.02, 0), 20)})
    b = S({'F3': (500.0, 25)},
          {'F3': SpectrumValue(Value(1, 0.1, 0), 30)})
    t = SpectrumSet({'a': a, 'b': b}).tabularProvider()

    # 440.0 loses its ".0", but 438.5 isn't merged with anything
    assert t.getHeaders() == ['name', 'm438.5', 's438.5', 'n438.5',
                              'm440', 's440', 'n440',
                              'm500', 's500', 'n500']

    rows = list(t)
    assert rows == [
        {'name': 'a',
         'm438.5': '0.5', 's438.5': '0.02', 'n438.5': '20',
         'm440': '0.25', 's440': '0.01', 'n440': '10',
         'm500': 'NA', 's500': 'NA', 'n500': '0'},
        {'name': 'b',
         'm438.5': 'NA', 's438.5': 'NA', 'n438.5': '0',
         'm440': 'NA', 's440': 'NA', 'n440': '0',
         'm500': '1', 's500': '0.1', 'n500': '30'},
    ]


def test_tabular_provider_duplicate_wavelength():
    """Two filters at the same wavelength in one spectrum can't both be shown, so that's an error."""
    a = S({'F1': (440, 25), 'F2': (440, 30)},
          {'F1': SpectrumValue(Value(0.25, 0.01, 0), 10),
           'F2': SpectrumValue(Value(0.5, 0.02, 0), 20)})
    with pytest.raises(ValueError):
        SpectrumSet({'a': a}).tabularProvider()


def test_tabular_provider_natural_row_order():
    """Rows are sorted by name, comparing runs of digits as numbers - so multidot's "2" comes before
    its "10", and "img2:..." before "img10:...", which a plain string sort gets wrong."""
    names = ['10', 'img10:1', '2', 'in0', 'img2:1', '0', 'img2:10', 'img2:2', '1']
    spectra = {n: S({'F1': (440, 25)}, {'F1': SpectrumValue(Value(1, 0.1, 0), 10)}) for n in names}
    rows = [r['name'] for r in SpectrumSet(spectra).tabularProvider()]
    assert rows == ['0', '1', '2', '10', 'img2:1', 'img2:2', 'img2:10', 'img10:1', 'in0']


def make_indexable_spectra():
    """A spectra Datum for the indexing tests: spectrum "0" has a saturated value at 440 and a fractional
    wavelength at 438.5; "fish" has 440 and 500."""
    from pcot import dq
    from pcot.sources import nullSourceSet
    ssd = SpectrumSet({
        '0': S({'F1': (440, 25), 'F2': (438.5, 25)},
               {'F1': SpectrumValue(Value(0.25, 0.01, dq.SAT), 10),
                'F2': SpectrumValue(Value(0.5, 0.02, dq.NONE), 20)}),
        'fish': S({'F1': (440, 25), 'F3': (500, 25)},
                  {'F1': SpectrumValue(Value(0.75, 0.03, dq.NONE), 30),
                   'F3': SpectrumValue(Value(1.5, 0.04, dq.NONE), 40)}),
    })
    return Datum(Datum.SPECTRA, ssd, sources=nullSourceSet)


def test_spectra_indexing():
    """Spectra can be indexed in expressions by name and wavelength, giving the stored Value with its
    uncertainty and DQ, or by name and column name as when spectra were output as tables."""
    from pcot import dq
    from pcot.expressions import ExpressionEvaluator
    e = ExpressionEvaluator()
    a = make_indexable_spectra()

    def run(expr):
        r = e.run(expr, {"a": a})
        assert r.tp == Datum.NUMBER
        return r.val

    # by wavelength - the stored value, DQ and all
    assert run("a[0,440]").approxeq(Value(0.25, 0.01, dq.SAT))
    assert run("a[0,438.5]").approxeq(Value(0.5, 0.02, dq.NONE))
    assert run("a[fish,500]").approxeq(Value(1.5, 0.04, dq.NONE))

    # table-style mean and SD of the same wavelength is the stored value too, so keeps its DQ
    assert run("a[0,m440,s440]").approxeq(Value(0.25, 0.01, dq.SAT))
    # a single column has no uncertainty, as with tables
    assert run("a[0,m440]").approxeq(Value(0.25, 0, dq.NOUNCERTAINTY))
    assert run("a[0,s440]").approxeq(Value(0.01, 0, dq.NOUNCERTAINTY))
    assert run("a[fish,n500]").approxeq(Value(40, 0, dq.NOUNCERTAINTY))
    # mixing wavelengths just pairs the two numbers up, with no DQ
    assert run("a[fish,m440,s500]").approxeq(Value(0.75, 0.04, dq.NONE))


@pytest.mark.parametrize("expr,message", [
    ("a[0,500]", "no value at wavelength 500"),
    ("a[7,440]", "no spectrum called 7"),
    ("a[1.5,440]", "not a whole number"),
    ("a[0,m500]", "has no column m500"),
    ("a[0,x440]", "bad spectrum column x440"),
    ("a[0]", "need a name and a wavelength or column"),
    ("a[0,440,s440]", "third index can only be used with column names"),
])
def test_spectra_indexing_errors(expr, message):
    """Unknown spectra, wavelengths and columns are errors rather than NA strings"""
    from pcot.expressions import ExpressionEvaluator
    with pytest.raises(Exception, match=message):
        ExpressionEvaluator().run(expr, {"a": make_indexable_spectra()})


def make_spectra_with_real_filter():
    """Two spectra which share a filter with a measured (non-simulated) response, and have one
    simulated filter each. One has a colour, the other doesn't."""
    import numpy as np
    from pcot import dq
    from pcot.cameras.filtresponse import FilterResponse
    resp = FilterResponse(None, wavelengths=np.array([400.0, 440.0, 480.0]), values=np.array([0.1, 0.9, 0.2]))
    shared = Filter(440, 25, transmission=0.8, position="L01", name="G01", camera_name="TESTCAM",
                    description="a real filter", response=resp)
    simA = Filter(500, 30, name="G02", camera_name="TESTCAM")
    simB = Filter(600, 30, name="G03", camera_name="TESTCAM")
    a = Spectrum({shared: SpectrumValue(Value(0.25, 0.01, dq.SAT), 10),
                  simA: SpectrumValue(Value(0.5, 0.02, dq.NONE), 20)}, colour=(1, 0, 0))
    b = Spectrum({shared: SpectrumValue(Value(0.75, 0.03, dq.NONE), 30),
                  simB: SpectrumValue(Value(1.5, 0.04, dq.NONE), 40)})
    return SpectrumSet({'a': a, 'b': b})


def check_spectra_with_real_filter(ss):
    """Check a (possibly round-tripped) set from make_spectra_with_real_filter"""
    import numpy as np
    from pcot import dq
    assert list(ss.keys()) == ['a', 'b']
    a, b = ss['a'], ss['b']
    assert a.colour == (1.0, 0.0, 0.0)
    assert b.colour is None
    # all the filter fields survive, and the shared filter is still a single object
    fa, fb = a.filters()[0], b.filters()[0]
    assert fa is fb
    assert (fa.cwl, fa.fwhm, fa.transmission, fa.position, fa.name, fa.camera_name, fa.description) == \
           (440, 25, 0.8, "L01", "G01", "TESTCAM", "a real filter")
    # including the measured response
    assert not fa.response.is_simulated
    assert np.allclose(fa.response.getResponse(np.array([400.0, 440.0, 480.0])), [0.1, 0.9, 0.2])
    assert a.filters()[1].response.is_simulated
    # and the values, with their uncertainty, DQ and pixel counts
    assert a.get(440).v.approxeq(Value(0.25, 0.01, dq.SAT))
    assert a.get(440).samples == 10
    assert a.get("G02").v.approxeq(Value(0.5, 0.02, dq.NONE))
    assert b.get(440).v.approxeq(Value(0.75, 0.03, dq.NONE))
    assert b.get(600).samples == 40


def test_spectrum_set_serialise_shares_filters():
    """Filters used by more than one spectrum are only stored once, and everything else survives a
    round trip - filter data (including measured responses), colours and values."""
    ss = make_spectra_with_real_filter()
    data = ss.serialise()
    # three distinct filters, even though there are four values
    assert len(data["filters"]) == 3
    check_spectra_with_real_filter(SpectrumSet.deserialise(data))


def test_spectra_parc_round_trip(tmp_path):
    """Spectra can be saved to and loaded from PARC files, keeping their sources"""
    from pcot.sources import SourceSet, Source
    from pcot.utils.archive import FileArchive
    from pcot.utils.datumstore import DatumStore
    ss = make_spectra_with_real_filter()
    ss.sources = SourceSet(Source().setBand("G01"))
    d = Datum(Datum.SPECTRA, ss, sources=ss.sources)
    d.save(tmp_path / "spectra.parc")

    # in read mode, the archive isn't opened with a context manager
    d2 = DatumStore(FileArchive(tmp_path / "spectra.parc")).get("main")
    assert d2.tp == Datum.SPECTRA
    check_spectra_with_real_filter(d2.val)
    assert d2.getSources().brief() == d.getSources().brief()
    assert d2.val.getSources().brief() == d.getSources().brief()


def test_spectrum_set_merge():
    """Names from the base are kept; names in parts are prefixed with the part's key only if they clash"""
    from pcot.sources import SourceSet, Source
    v = SpectrumValue(Value(1, 0.1, 0), 10)
    base = SpectrumSet({'1': S({'F1': (440, 25)}, {'F1': v}), 'in0': S({'F1': (440, 25)}, {'F1': v})},
                       SourceSet(Source().setBand("A")))
    p1 = SpectrumSet({'1': S({'F2': (500, 25)}, {'F2': v}), 'x': S({'F2': (500, 25)}, {'F2': v})},
                     SourceSet(Source().setBand("B")))
    p2 = SpectrumSet({'x': S({'F3': (600, 25)}, {'F3': v}), 'y': S({'F3': (600, 25)}, {'F3': v})},
                     SourceSet(Source().setBand("C")))
    m = SpectrumSet.merge({'in5': p1, 'in6': p2}, base=base)
    assert set(m.keys()) == {'1', 'in0', 'in5:1', 'in5:x', 'in6:x', 'y'}
    assert m['in5:1'] is p1['1']
    assert m['y'] is p2['y']
    assert sorted(s.band for s in m.getSources().sourceSet) == ['A', 'B', 'C']

    # a prefixed name which still clashes is an error rather than losing a spectrum
    base = SpectrumSet({'in5:1': S({'F1': (440, 25)}, {'F1': v}), '1': S({'F1': (440, 25)}, {'F1': v})})
    with pytest.raises(ValueError, match="in5:1 appears more than once"):
        SpectrumSet.merge({'in5': p1}, base=base)


def test_spectrum_node_spectra_input():
    """A spectrum node can take another spectrum node's output as well as images, and plots
    the same spectra with the same colours and filters"""
    pcot.setup()
    doc = Document()
    gen = doc.graph.create("gen")
    gen.params.imgwidth, gen.params.imgheight = 64, 64
    gen.params.chans.append_default().set(2, 10, 100, "gradient-x")
    gen.params.chans.append_default().set(3, 20, 200, "gradient-y")

    roi = doc.graph.create("rect")
    roi.connect(0, gen, 0)
    roi.roi.set(10, 10, 20, 20)

    first = doc.graph.create("spectrum")
    first.connect(0, roi, 0)
    second = doc.graph.create("spectrum")
    second.connect(0, gen, 0)       # an image with no ROI gives a spectrum called "in0"
    second.connect(1, first, 0)     # spectra, which include one called "1" (the rect's label)
    doc.run()

    assert first.error is None
    assert second.error is None
    s1 = first.getOutput(0, Datum.SPECTRA)
    s2 = second.getOutput(0, Datum.SPECTRA)
    label = list(s1.keys())[0]
    # the spectra input's names don't clash with the image's, so are unchanged
    assert set(s2.keys()) == {"in0", label}
    assert s2[label] is s1[label]
    # and the sources are from both inputs
    assert s2.getSources().brief() == second.getOutput(0).getSources().brief()
    assert s1.getSources().sourceSet <= s2.getSources().sourceSet


def test_spectrum_node_bad_input():
    """Connecting something which isn't an image or spectra is an error"""
    pcot.setup()
    doc = Document()
    const = doc.graph.create("constant")
    spec = doc.graph.create("spectrum")
    spec.connect(2, const, 0)
    doc.run()
    assert spec.error is not None
    assert "input 2 must be an image or spectra" in spec.error.message


@pytest.fixture
def provider_settings():
    """Lets a test change the spectra table settings, restoring the defaults afterwards"""
    P = SpectrumSet.Provider

    def setter(format, orientation):
        P.config = P.PROVIDER_PARAMS.create()
        P.config.format = format
        P.config.orientation = orientation

    yield setter
    P.config = P.PROVIDER_PARAMS.create()


def awkward_spectra():
    """the same spectra as test_tabular_provider_awkward_spectra"""
    a = S({'F1': (440.0, 25), 'F2': (438.5, 25)},
          {'F1': SpectrumValue(Value(0.25, 0.01, 0), 10),
           'F2': SpectrumValue(Value(0.5, 0.02, 0), 20)})
    b = S({'F3': (500.0, 25)},
          {'F3': SpectrumValue(Value(1, 0.1, 0), 30)})
    return SpectrumSet({'b': b, 'a': a})


@pytest.mark.parametrize("format,orientation,expected", [
    ("separate", "wv_cols",
     "name,m438.5,s438.5,n438.5,m440,s440,n440,m500,s500,n500\n"
     "a,0.5,0.02,20,0.25,0.01,10,NA,NA,0\n"
     "b,NA,NA,0,NA,NA,0,1,0.1,30\n"),
    ("mean", "wv_cols",
     "name,m438.5,n438.5,m440,n440,m500,n500\n"
     "a,0.5,20,0.25,10,NA,0\n"
     "b,NA,0,NA,0,1,30\n"),
    ("combined", "wv_cols",
     "name,m438.5,n438.5,m440,n440,m500,n500\n"
     "a,0.5±0.02,20,0.25±0.01,10,NA,0\n"
     "b,NA,0,NA,0,1±0.1,30\n"),
    ("separate", "wv_rows",
     "wavelength,a mean,a sd,a samples,b mean,b sd,b samples\n"
     "438.5,0.5,0.02,20,NA,NA,0\n"
     "440,0.25,0.01,10,NA,NA,0\n"
     "500,NA,NA,0,1,0.1,30\n"),
    ("mean", "wv_rows",
     "wavelength,a mean,a samples,b mean,b samples\n"
     "438.5,0.5,20,NA,0\n"
     "440,0.25,10,NA,0\n"
     "500,NA,0,1,30\n"),
    ("combined", "wv_rows",
     "wavelength,a mean,a samples,b mean,b samples\n"
     "438.5,0.5±0.02,20,NA,0\n"
     "440,0.25±0.01,10,NA,0\n"
     "500,NA,0,1±0.1,30\n"),
])
def test_tabular_provider_settings(provider_settings, format, orientation, expected):
    """Each value format works with wavelengths as columns or as rows, and CSV output follows the settings"""
    provider_settings(format, orientation)
    ss = awkward_spectra()
    assert ss.tabularProvider().csvString() == expected
    # the old-style table follows the settings too
    assert str(ss.table()).replace('\r\n', '\n') == expected


def test_tabular_provider_settings_change_existing_provider(provider_settings):
    """A provider that is already being displayed changes when the settings do"""
    t = awkward_spectra().tabularProvider()
    assert t.getHeaders()[0] == "name"
    provider_settings("separate", "wv_rows")
    assert t.getHeaders()[0] == "wavelength"
    assert [r["wavelength"] for r in t] == ["438.5", "440", "500"]

