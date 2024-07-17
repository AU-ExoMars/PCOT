import pcot
from pcot.datum import Datum
from pcot.document import Document
from pcot.expressions import ExpressionEvaluator
import pcot.datumfuncs as df
from fixtures import *
from pcot.rois import ROICircle
from pcot.sources import nullSourceSet
from pcot.value import Value
from pcot.xform import XFormException


def test_none_out():
    # Some functions will return None if the image is None (or not an image).
    # Can we cope with this?
    r = df.flipv(Datum(Datum.IMG, None))
    assert r is None

    e = ExpressionEvaluator()
    r = e.run("flipv(a)", {"a": Datum(Datum.IMG, None)})
    assert r == Datum.null


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

    doc.run()

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
    node3.roi.set(128, 128, 16)  # small circle in centre

    # and connect a node to that which will do the dqmod

    node4 = doc.graph.create("dqmod")
    node4.connect(0, node3, 0)
    # we're going to set DQ in band zero if the nominal value is >= -1
    node4.band = None  # All bands
    node4.mod = "Set"  # set DQ bits
    node4.data = "Nominal"
    node4.test = "Greater than or equal to"
    node4.value = -1
    node4.dq = dq.DIVZERO  # an arbitrary "BAD" bit to set

    # pass that into a node to strip the ROIs
    node5 = doc.graph.create("striproi")
    node5.connect(0, node4, 0)

    # run it, and pull out the result datum.
    doc.run()

    r = node5.getOutputDatum(0)

    assert r.get(Datum.IMG).rois == []

    # and run marksat on it!
    r = df.marksat(r)

    # make sure the DQs are as expected in the centre (i.e. not changed)
    img = r.get(Datum.IMG)
    dqs = [x.dq for x in img[130, 130]]
    assert dqs == [dq.DIVZERO | dq.NOUNCERTAINTY] * 3
    dqs = [x.dq for x in img[130, 126]]
    assert dqs == [dq.DIVZERO | dq.NOUNCERTAINTY] * 3

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
    assert [x.dq for x in img[128, 0]] == [dq.NOUNCERTAINTY, dq.ERROR | dq.NOUNCERTAINTY, dq.SAT | dq.NOUNCERTAINTY]
    assert [x.dq for x in img[200, 0]] == [dq.NOUNCERTAINTY, dq.ERROR | dq.NOUNCERTAINTY, dq.SAT | dq.NOUNCERTAINTY]
    assert [x.dq for x in img[205, 0]] == [dq.SAT | dq.NOUNCERTAINTY, dq.ERROR | dq.NOUNCERTAINTY,
                                           dq.SAT | dq.NOUNCERTAINTY]
    assert [x.dq for x in img[255, 0]] == [dq.SAT | dq.NOUNCERTAINTY, dq.ERROR | dq.NOUNCERTAINTY,
                                           dq.SAT | dq.NOUNCERTAINTY]


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


def test_striproi():
    r = df.testimg(1)

    # add an ROI
    rect = Datum(Datum.ROI, ROICircle(128, 128, 10), sources=nullSourceSet)
    withroi = df.addroi(r, rect)

    assert len(withroi.get(Datum.IMG).rois) == 1

    # strip it off
    r = df.striproi(withroi)
    assert len(r.get(Datum.IMG).rois) == 0
    # make sure it's still there on the original
    assert len(withroi.get(Datum.IMG).rois) == 1


def test_norm():
    r = df.testimg(1)
    unc = r * 0.01
    r = df.v(r, unc)

    # divide down
    a = r * 0.1
    # normalize
    b = df.norm(a)
    # should be the same as the original image - we're doing max to get the per-channel differences as a vector,
    # then max again to get the maximum of those.
    diffs = df.max(df.max(df.abs(b - r))).get(Datum.NUMBER).n
    assert diffs < 1e-7

    rpix = r.get(Datum.IMG)[255, 0]
    bpix = b.get(Datum.IMG)[255, 0]
    for x, y in zip(rpix, bpix):
        assert np.abs(x.n - y.n) < 1e-7
        assert np.abs(x.u - y.u) < 1e-7
        assert x.dq == y.dq

    # and test on subset
    a = df.addroi(a, Datum(Datum.ROI, ROICircle(128, 128, 30), sources=nullSourceSet))
    r = df.norm(a)
    pix = a.get(Datum.IMG)[127, 157]  # test original is still the same
    assert pix[0].approxeq(Value(0.04980392, 0.0004980392, dq.NONE))
    assert pix[1].approxeq(Value(0.06156862, 0.0006156863, dq.NONE))
    assert pix[2].approxeq(Value(0.10000000, 0.001, dq.NONE))

    pix = r.get(Datum.IMG)[127, 157]  # test normalised is correct
    assert pix[0].approxeq(Value(0.498039, 0.00498039, dq.NONE))
    assert pix[1].approxeq(Value(0.615686, 0.00615686, dq.NONE))
    assert pix[2].approxeq(Value(1.0, 0.01, dq.NONE))

    # make sure that normalisation does not occur outside the ROI
    pix1 = a.get(Datum.IMG)[50, 50]
    pix2 = r.get(Datum.IMG)[50, 50]

    assert pix1[0].approxeq(pix2[0])
    assert pix1[1].approxeq(pix2[1])
    assert pix1[2].approxeq(pix2[2])

    # now test splitchans mode, where each channel is normalized separately. Again, there's an ROI
    r = df.norm(a, splitchans=1)
    pix = r.get(Datum.IMG)[127, 157]
    assert pix[0].approxeq(Value(0.48333337903022766, 0.021166663616895676, dq.NONE))
    assert pix[1].approxeq(Value(0.9833332896232605, 0.02616666443645954, dq.NONE))
    assert pix[2].approxeq(Value(1.0, 0.01, dq.NONE))

    # without ROI - because each channel has the same 0-1 range it will be the same as the first test.
    a = df.striproi(a)
    r = df.norm(a, splitchans=1)
    pix = r.get(Datum.IMG)[127, 157]
    assert pix[0].approxeq(Value(0.498039, 0.00498039, dq.NONE))
    assert pix[1].approxeq(Value(0.615686, 0.00615686, dq.NONE))
    assert pix[2].approxeq(Value(1.0, 0.01, dq.NONE))


def test_clamp_multiply():
    """test clamping of a multiplied value (i.e. clamping to 1), no roi"""
    r = df.testimg(1)
    unc = r * 0.01
    r = df.v(r, unc)
    # sanity check of test data
    pix = r.get(Datum.IMG)[128, 128]
    assert pix[0].approxeq(Value(0.501961, 0.00501961, dq.NONE))
    assert pix[1].approxeq(Value(0.501961, 0.00501961, dq.NONE))
    assert pix[2].approxeq(Value(0, 0, dq.NONE))

    # multiply up
    a = r * 2
    # clamp
    b = df.clamp(a)
    # and compare with the original image - at 50,50 the new image should be double the original.
    pixb = b.get(Datum.IMG)[50, 50]
    pixr = r.get(Datum.IMG)[50, 50]
    rat = [x.n / y.n for x, y in zip(pixb, pixr)]
    urat = [x.u / y.u for x, y in zip(pixb, pixr)]
    # just look at RG because B will be zero and we'd get a divide by zero
    assert np.allclose(rat[:2], [2, 2])
    assert np.allclose(urat[:2], [2, 2])
    assert np.isnan(rat[2]) and np.isnan(urat[2])  # check those divzeroes

    # now check somewhere else in the image. R and B will be clamped
    # so will be set to 1+-0 and nounc.
    pixb = b.get(Datum.IMG)[192, 64]
    pixr = r.get(Datum.IMG)[192, 64]
    assert pixb[0].approxeq(Value(1.0, 0, dq.NOUNCERTAINTY))
    assert pixb[2].approxeq(Value(1.0, 0, dq.NOUNCERTAINTY))

    # G will still be in a 2:1 ratio to the original image
    rat = pixb[1].n / pixr[1].n
    urat = pixb[1].u / pixr[1].u
    assert rat == 2


def test_clamp_subtract():
    """test clamping of a subtracted value (i.e. clamping to zero), no roi. We won't test ROI; we're using
    the same framework as norm so it should be fine."""

    r = df.testimg(1)
    unc = r * 0.01
    r = df.v(r, unc)

    # subtract
    a = r - 0.5
    # clamp
    b = df.clamp(a)

    # in the top-left quadrant all channels will be clamped to zero
    pix = b.get(Datum.IMG)[50, 50]
    assert pix[0].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert pix[1].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    assert pix[2].approxeq(Value(0, 0, dq.NOUNCERTAINTY))
    # at bottom right only the blue channel will be clamped
    pix = b.get(Datum.IMG)[255, 255]
    assert pix[0].approxeq(Value(0.5, 0.01, dq.NONE))
    assert pix[1].approxeq(Value(0.5, 0.01, dq.NONE))
    assert pix[2].approxeq(Value(0, 0, dq.NOUNCERTAINTY))


def test_curve():
    """The most cursory of tests for sigmoid curve"""

    r = df.testimg(1)
    unc = r * 0.01
    r = df.v(r, unc)

    pix = r.get(Datum.IMG)[128, 128]
    # sanity check of test data
    assert pix[0].approxeq(Value(0.501961, 0.00501961, dq.NONE))
    assert pix[1].approxeq(Value(0.501961, 0.00501961, dq.NONE))
    assert pix[2].approxeq(Value(0, 0, dq.NONE))

    # but we will add a roi

    r = df.addroi(r, Datum(Datum.ROI, ROICircle(128, 128, 30), sources=nullSourceSet))

    def sig(x, m, c):
        x = x - 0.5  # this is important!
        return 1 / (1 + np.exp(-m * (x + c)))

    # no args (m=1, c=0) and outside the ROI
    out = df.curve(r)
    pixout = out.get(Datum.IMG)[120, 157]
    pixorig = r.get(Datum.IMG)[120, 157]
    assert pixout[0].approxeq(pixorig[0])
    assert pixout[1].approxeq(pixorig[1])
    assert pixout[2].approxeq(pixorig[2])

    # and inside should be under the influence
    pixout = out.get(Datum.IMG)[130, 135]
    pixorig = r.get(Datum.IMG)[130, 135]
    assert np.allclose([x.n for x in pixout], [sig(x.n, 1, 0) for x in pixorig])

    # no uncertainty in the result data
    assert [x.u == 0 for x in pixout]
    assert [x.dq == dq.NOUNCERTAINTY for x in pixout]


def test_resize():
    """again, a fairly cursory test for resizing, and not testing all the modes."""

    # make a mono image, and resize it down, then make sure the corners are still correct.
    img = gen_two_halves(256, 256, (1,), (4.0,), (2,), (5.0,))
    d = Datum(Datum.IMG, img)
    result = df.resize(d, 32, 32).get(Datum.IMG)
    assert result.shape == (32, 32)
    assert result[0,0] == Value(1, 4.0, dq.NONE)
    assert result[31,0] == Value(1, 4.0, dq.NONE)
    assert result[0,31] == Value(2, 5.0, dq.NONE)
    assert result[31,31] == Value(2, 5.0, dq.NONE)

    # and let's do a 2-channel image and resize it up, using nearest neighbour
    img = gen_two_halves(32, 32, (1,2), (4.0,3.0), (2,7), (5.0,6.0))
    d = Datum(Datum.IMG, img)
    result = df.resize(d, 256, 256, "nearest").get(Datum.IMG)
    assert result.shape == (256, 256, 2)
    assert result[0,0][0] == Value(1, 4.0, dq.NONE)
    assert result[255,0][0] == Value(1, 4.0, dq.NONE)
    assert result[0,0][1] == Value(2, 3.0, dq.NONE)
    assert result[255,0][1] == Value(2, 3.0, dq.NONE)
    assert result[0,255][0] == Value(2, 5.0, dq.NONE)
    assert result[255,255][0] == Value(2, 5.0, dq.NONE)
    assert result[0,255][1] == Value(7, 6.0, dq.NONE)
    assert result[255,255][1] == Value(7, 6.0, dq.NONE)

