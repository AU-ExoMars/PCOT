"""
This file tests the fundamental functionality of the spectrum system. If you
want to look at tests for the spectrum XForm, check the graphs directory.
"""
import pcot
from pcot.datum import Datum
from pcot.document import Document
from pcot.rois import ROICircle
from pcot.utils.spectrum import Spectrum
from pcot.value import Value
from pcot.xforms.xformgen import ChannelData


def create_test_image1():
    """we're going to use a "standard image" made using the "gen" xform. To do this, I'm going to
    spin up PCOT and create a document with a gen node in it. If you want to look at this image,
    open the spectrum.pcot file in the test graph directory and look at the "gen check 2" node.

    This image has constant uncertainty (0).
    """
    pcot.setup()
    doc = Document()

    node = doc.graph.create("gen")
    node.imgwidth, node.imgheight = 256, 256
    node.imgchannels = [
        # n, u, wavelength, mode. For all these modes, N and U don't mean N and U; check
        # the gen node documentation for details. But basically we're creating two
        # stepped gradients and a checkerboard pattern in the different channels.
        ChannelData(2, 10, 100, "gradient-x"),
        ChannelData(3, 20, 200, "gradient-y"),
        ChannelData(25, 0, 300, "checkx")
    ]
    doc.changed()
    img = node.getOutput(0, Datum.IMG)
    assert img.channels == 3  # just to be sure
    return img


def get_dot(img, x, y, r=3):
    """get the spectrum of a small part of the image"""
    # first add an ROI to the image
    roi = ROICircle(x, y, r, label="testroi")
    img.rois.append(roi)
    return Spectrum(img, roi)


def test_spectrum():
    img = create_test_image1()
    assert img.channels == 3

    s = get_dot(img, 187, 211)
    # check we can get filters and values
    # by wavelength
    assert s.get(100) == Value(1, 0, 0)
    assert s.get(200) == Value(1, 0, 0)
    assert s.get(300) == Value(1, 1, 0)

    # just check non-existent filters return None
    assert s.get("fish") is None
    assert s.get(400) is None

    # try another dot with a straightforward variance
    s = get_dot(img, 62, 110)
    assert s.get(100) == Value(0, 0, 0)
    assert s.get(200) == Value(0.5, 0, 0)
    assert s.get(300) == Value(0, 0, 0)

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
    assert s.get(100) == Value(0, 0, 0)
    assert s.get(200) == Value(0.15384615384615385, 0.23076923076923078, 0)
    assert s.get(300) == Value(1, 1, 0)


def create_test_image2():
    """Another test image - this uses the "gen check 3" node and its descendants in the same
    graph as the previous test image. This one has a rather more complex uncertainty pattern."""
    pcot.setup()
    doc = Document()

    # generates the nominal values
    gen = doc.graph.create("gen")
    gen.imgwidth, gen.imgheight = 256, 256
    gen.imgchannels = [
        ChannelData(2, 10, 100, "gradient-x"),
        ChannelData(2, 20, 200, "gradient-y")
    ]

    # we want the 200 channel to be multiplied
    mult200 = doc.graph.create("expr")
    mult200.expr = "merge(a$100,a$200*0.5)"
    mult200.connect(0, gen, 0)

    # offset to get uncertainties
    offset = doc.graph.create("offset")
    offset.x, offset.y = 1, 1
    offset.connect(0, mult200, 0)
    # combine the two with an expression
    expr = doc.graph.create("expr")
    expr.expr = "v(a*0.5+0.3,b*0.2+0.1)"
    expr.connect(0, mult200, 0)
    expr.connect(1, offset, 0)

    doc.changed()
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
    assert s.get(100) == Value(0.6461538461538463, 0.2964284441230415, 0)

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

    assert s.get(200).approxeq(Value(0.4730769230769231, 0.18040060614705503, 0))





