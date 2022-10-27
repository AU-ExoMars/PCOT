import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *


def test_roi_single_image(allblack):
    """Test that a single 'standard operation' - one which uses modifyWithSub - works
    correctly on an image with a single ROI. ROIs and modifyWithSub are tested at a lower
    level in basic/test_roi.py; this tests that the layers above use the right code."""

    pcot.setup()
    doc = Document()

    assert doc.setInputDirect(0, allblack) is None
    inputNode = doc.graph.create("input 0")

    roiNode = doc.graph.create("rect")
    # set the rect node's ROIRect to be at (2,2) with width=3, height=4, so 12 pixels
    roiNode.roi.set(2, 2, 3, 4)
    # connect input 0 on self to output 0 in the input node
    roiNode.connect(0, inputNode, 0)

    exprNode = doc.graph.create("expr")
    exprNode.expr = "clip(a+4)"  # will add 4 to the value and clip to 1.
    exprNode.connect(0, roiNode, 0)

    doc.changed()
    img = exprNode.getOutput(0, Datum.IMG)
    assert np.sum(img.img) == 12 * 3  # right number of pixels changed for a 3 channel image


def test_roi_intersection(allblack):
    """Test using expr to intersect two ROIs"""
    pcot.setup()
    doc = Document()

    assert doc.setInputDirect(0, allblack) is None
    inputNode = doc.graph.create("input 0")

    # create a rectangular 3x3 ROI for the image - we don't add it, we ignore the ROI's image output
    roiNode1 = doc.graph.create("rect")
    roiNode1.roi.set(2, 2, 3, 3)
    roiNode1.connect(0, inputNode, 0)

    # another rectangular 3x3 ROI, this one offset 1 in both axes, so the intersection is 2x2.
    roiNode2 = doc.graph.create("rect")
    roiNode2.roi.set(3, 3, 3, 3)
    roiNode2.connect(0, inputNode, 0)

    # now create an expression node to intersect the two ROIs, taking its input from the ROI
    # outputs (not the images)
    exprNode = doc.graph.create("expr")
    exprNode.expr = "a*b"  # multiply = intersect for ROIs
    exprNode.connect(0, roiNode1, 2)
    exprNode.connect(1, roiNode2, 2)

    # take that intersected ROI and apply it to the image
    importNode = doc.graph.create("importroi")
    importNode.connect(0, inputNode, 0)
    importNode.connect(1, exprNode, 0)

    # now take that image with the intersected ROI and set it to white (by adding a large
    # number and clipping). The resulting image should have had 4 pixels set to white.
    setWhiteNode = doc.graph.create("expr")
    setWhiteNode.expr = "clip(a+4)"
    setWhiteNode.connect(0, importNode, 0)

    doc.changed()

    img = setWhiteNode.getOutput(0, Datum.IMG)
    assert np.sum(img.img) == 4 * 3  # right number of pixels changed for a 3 channel image


def test_roi_union_expr(allblack):
    """Test using expr to union two ROIs; this is the default operation but here we use expr"""
    pcot.setup()
    doc = Document()

    assert doc.setInputDirect(0, allblack) is None
    inputNode = doc.graph.create("input 0")

    # create a rectangular 3x3 ROI for the image - we don't add it, we ignore the ROI's image output
    roiNode1 = doc.graph.create("rect")
    roiNode1.roi.set(2, 2, 3, 3)
    roiNode1.connect(0, inputNode, 0)

    # another rectangular 3x3 ROI, this one offset 1 in both axes, so the union is 14 pixels.
    roiNode2 = doc.graph.create("rect")
    roiNode2.roi.set(3, 3, 3, 3)
    roiNode2.connect(0, inputNode, 0)

    # now create an expression node to union the two ROIs, taking its input from the ROI
    # outputs (not the images)
    exprNode = doc.graph.create("expr")
    exprNode.expr = "a+b"  # add = union for ROIs
    exprNode.connect(0, roiNode1, 2)
    exprNode.connect(1, roiNode2, 2)

    # take that intersected ROI and apply it to the image
    importNode = doc.graph.create("importroi")
    importNode.connect(0, inputNode, 0)
    importNode.connect(1, exprNode, 0)

    # now take that image with the union ROI and set it to white (by adding a large
    # number and clipping). The resulting image should have had 14 pixels set to white.
    setWhiteNode = doc.graph.create("expr")
    setWhiteNode.expr = "clip(a+4)"
    setWhiteNode.connect(0, importNode, 0)

    doc.changed()

    img = setWhiteNode.getOutput(0, Datum.IMG)
    assert np.sum(img.img) == 14 * 3  # right number of pixels changed for a 3 channel image


def test_roi_union(allblack):
    """Union two ROIs by applying them in series"""
    pcot.setup()
    doc = Document()

    assert doc.setInputDirect(0, allblack) is None
    inputNode = doc.graph.create("input 0")

    # apply a rectangular 3x3 ROI to the image
    roiNode1 = doc.graph.create("rect")
    roiNode1.roi.set(2, 2, 3, 3)
    roiNode1.connect(0, inputNode, 0)

    # another rectangular 3x3 ROI, this one offset 1 in both axes, so the union is 14 pixels.
    roiNode2 = doc.graph.create("rect")
    roiNode2.roi.set(3, 3, 3, 3)
    roiNode2.connect(0, roiNode1, 0)

    # now take that image with the union ROI and set it to white (by adding a large
    # number and clipping). The resulting image should have had 14 pixels set to white.
    setWhiteNode = doc.graph.create("expr")
    setWhiteNode.expr = "clip(a+4)"
    setWhiteNode.connect(0, roiNode2, 0)

    doc.changed()

    img = setWhiteNode.getOutput(0, Datum.IMG)
    assert np.sum(img.img) == 14 * 3  # right number of pixels changed for a 3 channel image


def test_roi_binop_image_lhs():
    """Test image with ROI on LHS of binary operation where RHS is image with no binop.
    The left image is entirely red, and has a square ROI in the middle.
    The right image is entirely green.
    Adding the two images should result in a red image with a yellow square."""

    pcot.setup()
    doc = Document()

    redimg = genrgb(50, 50, 1, 0, 0, doc=doc, inpidx=0)
    assert doc.setInputDirect(0, redimg) is None
    red = doc.graph.create("input 0", displayName="RED input")

    greenimg = genrgb(50, 50, 0, 1, 0, doc=doc, inpidx=1)
    assert doc.setInputDirect(1, greenimg) is None
    green = doc.graph.create("input 1", displayName="GREEN input")

    # add ROI to image on LHS (red)
    roi = doc.graph.create("rect")
    roi.roi.set(10, 10, 30, 30)
    roi.connect(0, red, 0)

    expr = doc.graph.create("expr")
    expr.expr = "a+b"
    expr.connect(0, roi, 0)  # left hand side (red) has ROI
    expr.connect(1, green, 0)  # right hand side (green) does not

    doc.changed()
    img = expr.getOutput(0, Datum.IMG)
    assert img is not None

    # assert that the area outside the ROI is from the LHS
    assert np.array_equal(img.img[0, 0], (1, 0, 0))
    # and that the area inside is from the sum.
    assert np.array_equal(img.img[20, 20], (1, 1, 0))
    # and check the image sum - it's a 50x50 image with one channel set, so that's 50*50,
    # plus the 30x30 region adding into another channel.
    assert np.sum(img.img) == 50 * 50 + 30 * 30


def test_roi_binop_image_rhs():
    """Test image with ROI on RHS of binary operation where LHS is image with no binop.
    The left image is entirely green.
    The right image is entirely blue and has a square ROI in the middle.
    Adding the two images should result in a green image with a cyan square."""

    pcot.setup()
    doc = Document()

    greenimg = genrgb(50, 50, 0, 1, 0, doc=doc, inpidx=0)
    assert doc.setInputDirect(0, greenimg) is None
    green = doc.graph.create("input 0", displayName="GREEN input")

    blueimg = genrgb(50, 50, 0, 0, 1, doc=doc, inpidx=1)
    assert doc.setInputDirect(1, blueimg) is None
    blue = doc.graph.create("input 1", displayName="Blue input")

    # add ROI to image on RHS (blue)
    roi = doc.graph.create("rect")
    roi.roi.set(10, 10, 30, 30)
    roi.connect(0, blue, 0)

    expr = doc.graph.create("expr")
    expr.expr = "a+b"
    expr.connect(0, green, 0)  # left hand side (green) has no ROI
    expr.connect(1, roi, 0)  # right hand side (blue) does not

    doc.changed()
    img = expr.getOutput(0, Datum.IMG)
    assert img is not None

    # assert that the area outside the ROI is from the LHS
    assert np.array_equal(img.img[0, 0], (0, 1, 0))
    # and that the area inside is from the sum.
    assert np.array_equal(img.img[20, 20], (0, 1, 1))
    # and check the image sum - it's a 50x50 image with one channel set, so that's 50*50,
    # plus the 30x30 region adding into another channel.
    assert np.sum(img.img) == 50 * 50 + 30 * 30


def test_rois_on_both_sides_of_binop():
    """Test that operations on two images (e.g. a+b) don't work when there is an ROI on both sides.
    This test looks overcomplicated, and that's because it is. Originally the principle was that if
    we had two unions of ROIs being fed into both sides of a binop, that the operation would only
    modify the intersection - with the LHS being passed through for the rest. This is OK, but really
    breaks the principle of least astonishment. If the user has fed two images with ROIs into a binary
    operation it probably means they've done something wrong. Therefore, we should throw an error."""

    pcot.setup()
    doc = Document()

    # make 2 images, one red and one blue. Make sure the input indices are correct
    # for the sources!
    redimg = genrgb(50, 50, 1, 0, 0, doc=doc, inpidx=0)  # red 50x50
    blueimg = genrgb(50, 50, 0, 0, 1, doc=doc, inpidx=1)  # blue 50x50

    assert doc.setInputDirect(0, redimg) is None
    assert doc.setInputDirect(1, blueimg) is None
    red = doc.graph.create("input 0")
    blue = doc.graph.create("input 1")

    # add different ROIs to each image, two in each one.
    roi1a = doc.graph.create("rect")
    roi1a.roi.set(10, 10, 30, 30)
    roi1a.connect(0, red, 0)

    roi1b = doc.graph.create("rect")
    roi1b.roi.set(10, 20, 30, 30)  # below the other. Union will be 10,10 30x40
    roi1b.connect(0, roi1a, 0)

    roi2a = doc.graph.create("rect")
    roi2a.roi.set(20, 10, 30, 30)
    roi2a.connect(0, blue, 0)

    roi2b = doc.graph.create("rect")
    roi2b.roi.set(20, 20, 30, 30)  # below the other. Union will be 20,10 30x40
    roi2b.connect(0, roi2a, 0)

    # feed both images into an expr, adding the two together.

    expr = doc.graph.create("expr")
    expr.expr = "a+b"
    expr.connect(0, roi1b, 0)
    expr.connect(1, roi2b, 0)

    doc.changed()
    img = expr.getOutput(0, Datum.IMG)

    assert img is None
    assert expr.error.message == "cannot have two images with ROIs on both sides of a binary operation"


def test_rois_same_on_both_sides():
    """It can happen that the ROIs on both sides of a binop are the same ROI, which is fine. This
    can happen when two channels of the same image are being manipulated."""
    pcot.setup()
    doc = Document()

    # make 2 images, one red and one blue. Make sure the input indices are correct
    # for the sources!
    greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # dark green
    assert doc.setInputDirect(0, greenimg) is None
    green = doc.graph.create("input 0", displayName="GREEN input")

    roi = doc.graph.create("rect")
    roi.roi.set(10, 10, 30, 30)
    roi.connect(0, green, 0)

    expr = doc.graph.create("expr")
    expr.expr = "a$R+a$G"
    expr.connect(0, roi, 0)

    doc.changed()
    img = expr.getOutput(0, Datum.IMG)
    assert img is not None


def _testinternal_image_and_scalar(exprString):
    """Performs imagewithroi+scalar and scalar+imagewithroi"""
    pcot.setup()
    doc = Document()

    greenimg = genrgb(50, 50, 0, 0.5, 0, doc=doc, inpidx=0)  # dark green
    assert doc.setInputDirect(0, greenimg) is None
    green = doc.graph.create("input 0", displayName="GREEN input")

    roi = doc.graph.create("rect")
    roi.roi.set(10, 10, 30, 30)
    roi.connect(0, green, 0)

    expr = doc.graph.create("expr")
    expr.expr = exprString
    expr.connect(0, roi, 0)

    doc.changed()
    img = expr.getOutput(0, Datum.IMG)
    assert img is not None

    # assert that the area outside the ROI is unchanged
    assert np.array_equal(img.img[0, 0], (0, 0.5, 0))
    # and that the area inside is from the sum (note rounding errors)
    assert np.allclose(img.img[20, 20], [0.2, 0.7, 0.2])

    assert np.sum(img.img) == 50 * 50 * 0.5 + 30 * 30 * 0.2 * 3


def test_roi_image_plus_scalar():
    """Test that a imageWithROI+scalar uses the ROI"""
    _testinternal_image_and_scalar("a+0.2")


def test_roi_image_plus_scalar():
    """Test that a imageWithROI+scalar uses the ROI"""
    _testinternal_image_and_scalar("0.2+a")


def perform_roi_op(exprString) -> ImageCube:
    """Perform a binop on two rect. ROIs: (10,10,30,30) and (20,20,30,30).
    The resulting ROI is used to add 1 to an all black 50x50 image."""
    pcot.setup()
    doc = Document()

    redimg = genrgb(50, 50, 1, 0, 0, doc=doc, inpidx=0)  # red 50x50
    assert doc.setInputDirect(0, redimg) is None
    red = doc.graph.create("input 0")

    roi1 = doc.graph.create("rect")
    roi1.roi.set(10, 10, 30, 30)
    roi1.connect(0, red, 0)

    roi2 = doc.graph.create("rect")
    roi2.roi.set(20, 20, 30, 30)
    roi2.connect(0, red, 0)

    expr = doc.graph.create("expr")
    expr.expr = exprString
    expr.connect(0, roi1, 2)  # use the ROI output
    expr.connect(1, roi2, 2)

    importroi = doc.graph.create("importroi")
    importroi.connect(0, red, 0)
    importroi.connect(1, expr, 0)

    expr2 = doc.graph.create("expr")
    expr2.expr = "a+1"
    expr2.connect(0, importroi, 0)

    # doc.save("c:/users/jim/xxxx.pcot")

    doc.changed()
    img = expr2.getOutput(0, Datum.IMG)
    assert img is not None
    return img


def test_roi_intersection_expr():
    """Test that we can intersect two ROIs correctly with expr and importroi"""
    img = perform_roi_op("a*b")

    for x in range(0, 50):
        for y in range(0, 50):
            pix = img.img[y, x]
            expected = (2, 1, 1) if 20 <= x < 40 and 20 <= y < 40 else (1, 0, 0)
            assert np.array_equal(pix, expected)


def test_roi_union_expr():
    """Test that we can union two ROIs correctly with expr and importroi"""
    img = perform_roi_op("a+b")

    for x in range(0, 50):
        for y in range(0, 50):
            pix = img.img[y, x]
            in1 = 10 <= x < 40 and 10 <= y < 40
            in2 = 20 <= x < 50 and 20 <= y < 50
            expected = (2, 1, 1) if in1 or in2 else (1, 0, 0)
            assert np.array_equal(pix, expected), f"pixel {x}, {y} should be {expected}, is {pix}"


def test_roi_diff_expr():
    """Test that we can difference two ROIs correctly with expr and importroi"""
    img = perform_roi_op("a-b")

    for x in range(0, 50):
        for y in range(0, 50):
            pix = img.img[y, x]
            in1 = 10 <= x < 40 and 10 <= y < 40
            in2 = 20 <= x < 50 and 20 <= y < 50
            expected = (2, 1, 1) if in1 and not in2 else (1, 0, 0)
            assert np.array_equal(pix, expected), f"pixel {x}, {y} should be {expected}, is {pix}"


def test_roi_diff_exp2():
    """Test that we can difference two ROIs correctly with expr and importroi"""
    img = perform_roi_op("b-a")

    for x in range(0, 50):
        for y in range(0, 50):
            pix = img.img[y, x]
            in1 = 10 <= x < 40 and 10 <= y < 40
            in2 = 20 <= x < 50 and 20 <= y < 50
            expected = (2, 1, 1) if in2 and not in1 else (1, 0, 0)
            assert np.array_equal(pix, expected), f"pixel {x}, {y} should be {expected}, is {pix}"


def test_roi_neg_expr_unimplemented():
    """Unary negate is not implemented (yet?)"""

    pcot.setup()
    doc = Document()

    redimg = genrgb(50, 50, 1, 0, 0, doc=doc, inpidx=0)  # red 50x50
    assert doc.setInputDirect(0, redimg) is None
    red = doc.graph.create("input 0")

    roi1 = doc.graph.create("rect")
    roi1.roi.set(10, 10, 30, 30)
    roi1.connect(0, red, 0)

    expr = doc.graph.create("expr")
    expr.expr = "-a"
    expr.connect(0, roi1, 2)  # use the ROI output

    doc.changed()

    assert expr.error.message == "incompatible type for operator NEG: roi"
