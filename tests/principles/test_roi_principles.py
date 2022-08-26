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

    # another rectangular 3x3 ROI, this one offset 1 in both axes, so the intersect is 2x2.
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


def test_roi_intersection_node(allblack):
    """Test ROI intersection node"""
    pytest.fail("Not yet implemented")


def test_roi_binop_intersection_of_union():
    """Test that operations on two images (e.g. a+b) take place only on the intersection
    of the unions of the ROIs in the images - on the ROI given by
    intersect(union(rois_a),union(rois_b))"""

    pcot.setup()
    doc = Document()

    # make 2 images, one red and one blue.
    redimg = genrgb(50, 50, 1, 0, 0)  # red 50x50
    blueimg = genrgb(50, 50, 0, 0, 1)  # blue 50x50

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
    img = expr.getOutput(0,Datum.IMG)

    pytest.fail("Not yet tested and current principle needs thought")
