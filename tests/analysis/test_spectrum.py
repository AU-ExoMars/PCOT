"""
This file tests the fundamental functionality of the spectrum system. If you
want to look at tests for the spectrum XForm, check the graphs directory.
"""
import os

import pcot
from pcot.datum import Datum
from pcot.document import Document
from pcot.rois import ROICircle, ROIRect, ROI
from pcot.utils.spectrum import Spectrum, SpectrumSet, NameResolver
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
    return Spectrum(img, roi)


def test_coalesce():
    """Test that ROIs with the same name are combined into one ROI, but not across images"""

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

    # now we'll build the dict that coalence (and SpectrumSet) works on
    d = {
        'img1': img1,
        'img2': img2
    }
    # and coalesce
    SpectrumSet._coalesceROIs(d)
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
    SpectrumSet._coalesceROIs(d)
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
    # test pixel counts work
    assert s.get(100).pixels == 29
    assert s.get(200).pixels == 29
    assert s.get(300).pixels == 29

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
    assert s.get(100).pixels == 13  # test the pixel count works!

    # check we can get by index
    assert s.getByChannel(0).v == Value(0, 0, 0)
    assert s.getByChannel(1).v == Value(0.15384615384615385, 0.23076923076923078, 0)
    assert s.getByChannel(2).v == Value(1, 1, 0)


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
    ss1 = SpectrumSet({"in0": gen1img, "in4": md1img})
    t = str(ss1.table()).strip().replace('\r\n', '\n')
    assert t == res1

    # same with md2
    res2 = doc.graph.getByDisplayName("stringtest 2", single=True).params.string.strip().replace('\r\n', '\n')
    ss2 = SpectrumSet({"in0": md2img})
    t = str(ss2.table()).strip().replace('\r\n', '\n')
    assert t == res2

    # and finally the complex test with md3
    res3 = doc.graph.getByDisplayName("stringtest 3", single=True).params.string.strip().replace('\r\n', '\n')
    ss3 = SpectrumSet({
        "in0": gen1img,
        "in1": md1img,
        "in2": md2img,
        "in3": gen2img,
        "in4": md3img
    })
    t = str(ss3.table()).strip().replace('\r\n', '\n')
    assert t == res3
