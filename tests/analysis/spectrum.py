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


def create_test_image():
    """we're going to use a "standard image" made using the "gen" xform. To do this, I'm going to
    spin up PCOT and create a document with a gen node in it. If you want to look at this image,
    open the spectrum.pcot file in the test graph directory and look at the "gen check 2" node.
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


def test_spectrum():
    img = create_test_image()
    assert img.channels == 3

    def get_dot(x, y, r=3):
        """get the spectrum of a small part of the image"""
        # first add an ROI to the image
        roi = ROICircle(x, y, r, label="testroi")
        img.rois.append(roi)
        return Spectrum(img, roi)

    s = get_dot(187, 211)
    # check we can get filters and values
    # by wavelength
    assert s.get(100) == Value(1, 0, 0)
    assert s.get(200) == Value(1, 0, 0)
    assert s.get(300) == Value(1, 1, 0)

    # just check non-existent filters return None
    assert s.get("fish") is None
    assert s.get(400) is None

    # try another dot with a straightforward variance
    s = get_dot(62, 110)
    assert s.get(100) == Value(0, 0, 0)
    assert s.get(200) == Value(0.5, 0, 0)
    assert s.get(300) == Value(0, 0, 0)

    # and now one that straddes a boundary between regions
    # in a filter with a zero variance. Here, the 200 filter
    # is half 0.5 and half 0.0.
    # todo
    s = get_dot(62, 84, 3)  # radius of 3
    assert s.get(100) == Value(0, 0, 0)
    assert s.get(200) == Value(0, 0, 0)
    assert s.get(300) == Value(0, 0, 0)

    # need to also check pooled variance
    # todo




