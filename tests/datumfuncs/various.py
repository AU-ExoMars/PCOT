import pcot
from pcot.datum import Datum
from pcot.document import Document
from pcot.expressions import ExpressionEvaluator
import pcot.expressions.funcs as df
from fixtures import *
from pcot.rois import ROICircle
from pcot.sources import nullSourceSet
from pcot.value import Value
from pcot.xform import XFormException


def test_merge():
    # get the test image
    r = df.testimg(0)

    # extract the red, green and blue channels
    red = r % "R"
    green = r % "G"
    blue = r % "B"

    for img in [red, green, blue]:
        assert img.get(Datum.IMG).channels == 1
        assert img.get(Datum.IMG).shape == (256, 256)

    # merge them back together
    merged = df.merge(red, green, blue)

    # check that the merged image has three channels
    assert merged.get(Datum.IMG).channels == 3
    assert merged.get(Datum.IMG).shape == (256, 256, 3)

    # subtract this image from the original
    diff = r - merged
    # and check the resulting numbers are tiny
    n = diff.get(Datum.IMG).img
    assert np.abs(n).max() < 1e-10

    # put it back together differently for fun and make sure it's different
    merged = df.merge(blue, red, green)
    diff = r - merged
    n = diff.get(Datum.IMG).img
    assert np.abs(n).max() > 0.01


def test_grey_and_optional_args_py(rectimage):
    """This tests both the grey() function and a single optional argument from python."""
    r = df.testimg(0)
    g1 = df.grey(r)
    assert g1.get(Datum.IMG).channels == 1
    assert g1.get(Datum.IMG).shape == (256, 256)

    # do it the OpenCV way
    g2 = df.grey(r, 1)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() > 1e-10

    # do it the OpenCV way, providing the kwarg by name
    g2 = df.grey(r, opencv=1)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() > 1e-10

    # now with the opencv argument as zero.
    g2 = df.grey(r, 0)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() < 1e-10

    g2 = df.grey(r, opencv=0)
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() < 1e-10


def test_grey_and_optional_args_expr():
    """This tests both the grey() function and a single optional argument from ExpressionEvaluator."""
    r = df.testimg(0)
    e = ExpressionEvaluator()
    g1 = e.run("grey(a)", {'a': r})
    assert g1.get(Datum.IMG).channels == 1
    assert g1.get(Datum.IMG).shape == (256, 256)

    # do it the OpenCV way
    g2 = e.run("grey(a, 1)", {'a': r})
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() > 1e-10

    # NOTE - no keyword arguments in ExpressionEvaluator!

    # now with the opencv argument as zero.
    g2 = e.run("grey(a, 0)", {'a': r})
    assert g2.get(Datum.IMG).channels == 1
    assert g2.get(Datum.IMG).shape == (256, 256)
    img = (g1 - g2).get(Datum.IMG).img
    assert np.abs(img).max() < 1e-10


def test_crop(rectimage):
    d = Datum(Datum.IMG, rectimage)

    r = df.crop(d, 0, 0, 3, 3).get(Datum.IMG).img
    assert r.shape == (3, 3, 3)
    # top left corner is orange
    assert np.allclose(r[0, 0], [1, 0.6, 0.2])

    r = df.crop(d, 38, 28, 2, 2).get(Datum.IMG).img
    assert r.shape == (2, 2, 3)
    # bottom right is cyan
    assert np.allclose(r[0, 0], [0.3019608, 0.8, 0.6])

    # also works with coords too big
    r = df.crop(d, 38, 28, 20, 20).get(Datum.IMG).img
    assert r.shape == (2, 2, 3)
    # bottom right is cyan
    assert np.allclose(r[0, 0], [0.3019608, 0.8, 0.6])

    with pytest.raises(XFormException):
        r = df.crop(d, -3, -3, 6, 6).get(Datum.IMG).img

    with pytest.raises(XFormException):
        r = df.crop(d, 1, 1, 0, 0).get(Datum.IMG).img

    with pytest.raises(XFormException):
        r = df.crop(d, 1, 1, -2, -2).get(Datum.IMG).img


def test_rgb():
    # We'll just do this by converting a greyscale image to RGB; all the channels
    # should be the same.
    r = df.testimg(0)
    g = df.grey(r)
    assert g.get(Datum.IMG).channels == 1
    assert g.get(Datum.IMG).shape == (256, 256)

    # convert to RGB
    r = df.rgb(g)
    assert r.get(Datum.IMG).channels == 3
    assert r.get(Datum.IMG).shape == (256, 256, 3)

    # and check that all the channels are the same
    for i in range(3):
        assert np.allclose(r.get(Datum.IMG).img[:, :, i], g.get(Datum.IMG).img)


def test_v():
    r = df.testimg(0)
    assert np.all(r.get(Datum.IMG).dq == np.array([
        dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY],
        dtype=np.uint16))

    # apply an uncertainty to the image
    r = df.v(r, 0.1)  # numeric values are converted to Datum
    pix = r.get(Datum.IMG).img[0, 0]
    unc = r.get(Datum.IMG).uncertainty[0, 0]
    assert np.allclose(pix, [0.3882353, 0.21960784, 0.13725491])
    # and check that the uncertainty is set
    assert np.allclose(unc, [0.1, 0.1, 0.1])
    assert np.all(r.get(Datum.IMG).dq == np.array([0, 0, 0], dtype=np.uint16))

    # now apply an uncertainty which is 0.1 times the nominal of each pixel
    r = df.testimg(0)
    r = df.v(r, 0.1 * r)
    pix = r.get(Datum.IMG).img[0, 0]
    unc = r.get(Datum.IMG).uncertainty[0, 0]
    assert np.allclose(pix, [0.3882353, 0.21960784, 0.13725491])
    assert np.allclose(unc, [0.03882353, 0.021960784, 0.013725491])

    # now apply a fixed nominal to an uncertainty (a bit weird)
    r = df.testimg(0)
    r = df.v(0.1, r)
    pix = r.get(Datum.IMG).img[0, 0]
    unc = r.get(Datum.IMG).uncertainty[0, 0]
    assert np.allclose(unc, [0.3882353, 0.21960784, 0.13725491])
    # and check that the uncertainty is set
    assert np.allclose(pix, [0.1, 0.1, 0.1])
    assert np.all(r.get(Datum.IMG).dq == np.array([0, 0, 0], dtype=np.uint16))

    # finally generate a value
    r = df.v(0.1, 0.01)
    assert r.get(Datum.NUMBER).n == np.float32(0.1)
    assert r.get(Datum.NUMBER).u == np.float32(0.01)
    assert r.get(Datum.NUMBER).dq == dq.NONE

    # Here we are creating a value with an uncertainty of 0.0. There is still uncertainty
    # data, but it is 0.0. We don't want to treat this as a value with no uncertainty.
    r = df.v(0.1, 0.0)
    assert r.get(Datum.NUMBER).n == np.float32(0.1)
    assert r.get(Datum.NUMBER).u == np.float32(0.0)
    assert r.get(Datum.NUMBER).dq == dq.NONE

    # finally add some dq to an image, deleting all the uncertainty
    # (but not setting the uncertainty bit)
    r = df.testimg(0)
    r = df.v(r, dqbits=dq.ERROR)
    pix = r.get(Datum.IMG).img[0, 0]
    unc = r.get(Datum.IMG).uncertainty[0, 0]
    assert np.allclose(pix, [0.3882353, 0.21960784, 0.13725491])
    # and check that the uncertainty is set
    assert np.allclose(unc, [0, 0, 0])
    assert np.all(r.get(Datum.IMG).dq == np.array([dq.ERROR, dq.ERROR, dq.ERROR], dtype=np.uint16))


def test_nominal_and_uncertainty():
    r = df.testimg(0)
    n = df.nominal(r)
    u = df.uncertainty(r)
    assert np.allclose(n.get(Datum.IMG).img, r.get(Datum.IMG).img)
    assert np.allclose(u.get(Datum.IMG).img, r.get(Datum.IMG).uncertainty)

    # the resulting images should have no uncertainty
    assert np.allclose(n.get(Datum.IMG).uncertainty, 0)
    assert np.allclose(u.get(Datum.IMG).uncertainty, 0)

    # and should be marked in the dq bits as such

    assert np.all(n.get(Datum.IMG).dq == np.array([
        dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY],
        dtype=np.uint16))
    assert np.all(u.get(Datum.IMG).dq == np.array([
        dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY],
        dtype=np.uint16))


def test_marksat():
    r = df.testimg(1)
    assert r.get(Datum.IMG).countBadPixels() == 0

    r = df.marksat(r)
    img = r.get(Datum.IMG)
    assert img.channels == 3
    assert img.shape == (256, 256, 3)
    assert img.countBadPixels() == 65536  # all pixels will be bad!

    # top left corner is all zeroes, so error.
    assert np.all(img.dq[0, 0] == [dq.ERROR | dq.NOUNCERTAINTY] * 3)

    # bottom left corner (0,1,1)
    dqs = [x.dq for x in img[0, 255]]
    assert dqs == [dq.ERROR | dq.NOUNCERTAINTY,
                   dq.SAT | dq.NOUNCERTAINTY,
                   dq.SAT | dq.NOUNCERTAINTY]

    # bottom right corner (1,1,0)
    dqs = [x.dq for x in img[255, 255]]
    assert dqs == [dq.SAT | dq.NOUNCERTAINTY,
                   dq.SAT | dq.NOUNCERTAINTY,
                   dq.ERROR | dq.NOUNCERTAINTY]

    dqs = [x.dq for x in img[130, 130]]
    assert dqs == [dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY | dq.ERROR]

    dqs = [x.dq for x in img[130, 126]]
    assert dqs == [dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY | dq.SAT]

    # now mask off an area with an ROI
    rect = Datum(Datum.ROI, ROICircle(128, 128, 10), sources=nullSourceSet)
    r = df.addroi(df.testimg(1), rect)
    img = df.marksat(r).get(Datum.IMG)

    # edges should be unchanged (outside the ROI)
    dqs = [x.dq for x in img[255, 255]]
    assert dqs == [dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY]

    # but changed inside the ROI
    dqs = [x.dq for x in img[130, 130]]
    assert dqs == [dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY | dq.ERROR]

    dqs = [x.dq for x in img[130, 126]]
    assert dqs == [dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY | dq.SAT]


def test_marksat_masked():
    """Test that marksat doesn't set pixels with BAD already on them."""

    # here we need to use a dqmod, so we'll create a graph
    pcot.setup()
    doc = Document()

    # create a node which brings in that same image
    node1 = doc.graph.create("expr")
    node1.expr = "testimg(1)"

    # create a node which marksat's the image as a quick check
    node2 = doc.graph.create("expr")
    node2.expr = "marksat(a)"
    node2.connect(0, node1, 0)

    doc.changed()

    # get the output of node2 and check it has the same new DQs as in the
    # previous test
    img = node2.getOutput(0, Datum.IMG)
    dqs = [x.dq for x in img[130, 130]]
    assert dqs == [dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY | dq.ERROR]

    dqs = [x.dq for x in img[130, 126]]
    assert dqs == [dq.NOUNCERTAINTY, dq.NOUNCERTAINTY, dq.NOUNCERTAINTY | dq.SAT]

    # now connect a node to expr2 which masks off an area with an ROI

    node3 = doc.graph.create("circle")
    node3.connect(0, node1, 0)
    node3.roi.set(128, 128, 16)     #  small circle in centre

    # and connect a node to that which will do the dqmod

    node4 = doc.graph.create("dqmod")
    node4.connect(0, node3, 0)
    # we're going to set DQ in band zero if the nominal value is >= -1
    node4.band = None      # All bands
    node4.mod = "Set"   # set DQ bits
    node4.data = "Nominal"
    node4.test = "Greater than or equal to"
    node4.value = -1
    node4.dq = dq.DIVZERO       # an arbitrary "BAD" bit to set

    # pass that into a node to strip the ROIs
    node5 = doc.graph.create("striproi")
    node5.connect(0, node4, 0)

    # run it, and pull out the result datum.
    doc.changed()

    r = node5.getOutputDatum(0)

    assert r.get(Datum.IMG).rois == []

    # and run marksat on it!
    r = df.marksat(r)

    # make sure the DQs are as expected in the centre (i.e. not changed)
    img = r.get(Datum.IMG)
    dqs = [x.dq for x in img[130, 130]]
    assert dqs == [dq.DIVZERO|dq.NOUNCERTAINTY] * 3
    dqs = [x.dq for x in img[130, 126]]
    assert dqs == [dq.DIVZERO|dq.NOUNCERTAINTY] * 3

    # but have been set outside the region whose DQs we set to bad.
    dqs = [x.dq for x in img[255, 255]]
    assert dqs == [dq.SAT | dq.NOUNCERTAINTY,
                   dq.SAT | dq.NOUNCERTAINTY,
                   dq.ERROR | dq.NOUNCERTAINTY]


def test_marksat_args():
    r = df.testimg(1)

    # so this time, everything below 0.5 is ERROR and everything
    # greater than 0.8 is SAT.
    r = df.marksat(r, 0.5, 0.8)

    img = r.get(Datum.IMG)
    # top left corner is all zeroes, so error.
    assert [x.dq for x in img[0, 0]] == [dq.ERROR | dq.NOUNCERTAINTY] * 3
    assert [x.dq for x in img[20, 0]] == [dq.ERROR | dq.NOUNCERTAINTY] * 3
    assert [x.dq for x in img[127, 0]] == [dq.ERROR | dq.NOUNCERTAINTY] * 3
    assert [x.dq for x in img[128, 0]] == [dq.NOUNCERTAINTY,  dq.ERROR | dq.NOUNCERTAINTY, dq.SAT | dq.NOUNCERTAINTY]
    assert [x.dq for x in img[200, 0]] == [dq.NOUNCERTAINTY,  dq.ERROR | dq.NOUNCERTAINTY, dq.SAT | dq.NOUNCERTAINTY]
    assert [x.dq for x in img[205, 0]] == [dq.SAT | dq.NOUNCERTAINTY,  dq.ERROR | dq.NOUNCERTAINTY, dq.SAT | dq.NOUNCERTAINTY]
    assert [x.dq for x in img[255, 0]] == [dq.SAT | dq.NOUNCERTAINTY,  dq.ERROR | dq.NOUNCERTAINTY, dq.SAT | dq.NOUNCERTAINTY]


def test_setcwl():
    r = df.testimg(1)
    r = df.grey(r)
    r = df.setcwl(r, 340)

    img = r.get(Datum.IMG)
    assert img.channels == 1
    assert img.shape == (256, 256)

    cwl, fwhm = img.wavelengthAndFWHM(0)
    assert cwl == 340
    assert fwhm == 30


def test_flipv():
    # load a basic RGB image - no unc, no dq
    r = df.testimg(1)
    # create an uncertainty channel and add it
    unc = r*0.01
    r = df.v(r, unc)
    # test the top-right pixel just to make sure we created it right.
    pix = r.get(Datum.IMG)[255, 0]
    assert np.allclose([x.n for x in pix], [1, 0, 1])
    assert np.allclose([x.u for x in pix], [0.01, 0, 0.01])
    assert [x.dq for x in pix] == [0, 0, 0]
    # add DQ bits at the bottom left. Hack, and note the coordinate
    # reversal - the underlying arrays are [y,x] coordinate system
    r.get(Datum.IMG).dq[255, 0] = [dq.ERROR, dq.NONE, dq.SAT]
    pix = r.get(Datum.IMG)[0, 255]
    assert [x.dq for x in pix] == [dq.ERROR, dq.NONE, dq.SAT]

    r = df.flipv(r)
    img = r.get(Datum.IMG)
    assert img.channels == 3
    assert img.shape == (256, 256, 3)
    vals = [x.n for x in img[0, 0]]
    assert np.allclose(vals, [0, 1, 1])
    assert np.allclose([x.u for x in img[0, 0]], [0, 0.01, 0.01])
    assert [x.dq for x in img[0, 0]] == [dq.ERROR, dq.NONE, dq.SAT]


def test_fliph():
    # load a basic RGB image - no unc, no dq
    r = df.testimg(1)
    # create an uncertainty channel and add it
    unc = r*0.01
    r = df.v(r, unc)
    # add DQ bits at the top right. Hack, and note the coordinate
    # reversal - the underlying arrays are [y,x] coordinate system
    r.get(Datum.IMG).dq[0, 255] = [dq.ERROR, dq.NONE, dq.SAT]
    pix = r.get(Datum.IMG)[255, 0]
    assert [x.dq for x in pix] == [dq.ERROR, dq.NONE, dq.SAT]

    r = df.fliph(r)
    img = r.get(Datum.IMG)
    assert img.channels == 3
    assert img.shape == (256, 256, 3)
    vals = [x.n for x in img[0, 0]]
    assert np.allclose(vals, [1, 0, 1])
    assert np.allclose([x.u for x in img[0, 0]], [0.01, 0, 0.01])
    assert [x.dq for x in img[0, 0]] == [dq.ERROR, dq.NONE, dq.SAT]


def test_none_out():
    # Some functions will return None if the image is None (or not an image).
    # Can we cope with this?
    r = df.flipv(Datum(Datum.IMG, None))
    assert r is Datum.null


def test_rotate():
    r = df.testimg(1)
    unc = r*0.01
    r = df.v(r, unc)
    r.get(Datum.IMG).dq[0, 0] = [dq.ERROR, dq.NONE, dq.SAT]

    # topright becomes top-left
    r = df.rotate(r, 90)
    pix = r.get(Datum.IMG)[0,0]
    assert np.allclose([x.n for x in pix], [1, 0, 1])
    assert np.allclose([x.u for x in pix], [0.01, 0, 0.01])
    assert [x.dq for x in pix] == [0, 0, 0]
    # test it this way too - we'll just do this from now on.
    assert r.get(Datum.IMG)[0, 0] == (
        Value(1, 0.01, dq.NONE),
        Value(0, 0, dq.NONE),
        Value(1, 0.01, dq.NONE)
    )

    # check that the bottom left is OK too
    assert r.get(Datum.IMG)[0, 255] == (
        Value(0, 0, dq.ERROR),
        Value(0, 0, dq.NONE),
        Value(0, 0, dq.SAT)
    )

    # now try again with 270 (one turn clockwise)
    r = df.testimg(1)
    unc = r*0.01
    r = df.v(r, unc)
    r.get(Datum.IMG).dq[0, 0] = [dq.ERROR|dq.TEST, dq.NONE, dq.SAT]
    r = df.rotate(r, 270)

    assert r.get(Datum.IMG)[0, 0] == (
        Value(0, 0, dq.NONE),
        Value(1, 0.01, dq.NONE),
        Value(1, 0.01, dq.NONE)
    )
    assert r.get(Datum.IMG)[255, 0] == (
        Value(0, 0, dq.ERROR|dq.TEST),
        Value(0, 0, dq.NONE),
        Value(0, 0, dq.SAT)
    )

    # and again to check that -90 is 270. (Slightly different vals, though)
    r = df.testimg(1)
    unc = r*0.02
    r = df.v(r, unc)
    r.get(Datum.IMG).dq[0, 0] = [dq.ERROR|dq.TEST, dq.NONE, dq.SAT|dq.DIVZERO]
    r = df.rotate(r, -90)
    assert r.get(Datum.IMG)[0, 0] == (
        Value(0, 0, dq.NONE),
        Value(1, 0.02, dq.NONE),
        Value(1, 0.02, dq.NONE)
    )
    assert r.get(Datum.IMG)[255, 0] == (
        Value(0, 0, dq.ERROR|dq.TEST),
        Value(0, 0, dq.NONE),
        Value(0, 0, dq.SAT|dq.DIVZERO)
    )




