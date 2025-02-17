"""
Tests of functions related to ROIs.
"""
import pcot
from pcot.datum import Datum
from pcot.document import Document
from fixtures import *
import pcot.datumfuncs as df
from pcot.rois import ROIRect
from pcot.sources import nullSourceSet
from pcot.utils.geom import Rect


def test_roi(allblack):
    # we'll use a graph here to create the ROI
    pcot.setup()
    doc = Document()

    assert doc.setInputDirectImage(0, allblack) is None
    inputNode = doc.graph.create("input 0")
    roiNode = doc.graph.create("rect")
    # set the rect node's ROIRect to be at (2,2) with width=3, height=4, so 12 pixels
    roiNode.roi.set(2, 2, 3, 4)
    # connect input 0 on self to output 0 in the input node
    roiNode.connect(0, inputNode, 0)

    # and we'll first test using roi() in an expression node
    exprNode = doc.graph.create("expr")
    exprNode.params.expr = "roi(a)"  # will add 4 to the value and clip to 1.
    exprNode.connect(0, roiNode, 0)

    # now we'll run the graph
    doc.run()
    r = exprNode.getOutput(0, Datum.ROI)
    assert r.bb() == Rect(2, 2, 3, 4)

    # now add another ROI node and set it to overlap the first
    # and connect it to the output of the first ROI node
    roiNode2 = doc.graph.create("rect")
    roiNode2.roi.set(3, 3, 3, 3)
    roiNode2.connect(0, roiNode, 0)
    # reconnect the expr node to the second ROI node
    exprNode.connect(0, roiNode2, 0)

    doc.run()
    r = exprNode.getOutput(0, Datum.ROI)
    # the result should be the union of the two ROIs
    assert r.bb() == Rect(2, 2, 4, 4)

    # now just create an image and get the ROI on it. This time we'll use
    # the function directly

    t = df.testimg(0)
    r = df.roi(t)
    # the ROI on an image with no ROIs is the entire image
    assert r.get(Datum.ROI).bb() == Rect(0, 0, t.get(Datum.IMG).w, t.get(Datum.IMG).h)


def test_addroi():
    t = df.testimg(0)
    r = ROIRect(rect=(2, 2, 3, 4))
    r = df.addroi(t, Datum(Datum.ROI, r, sources=nullSourceSet))
    assert r.get(Datum.IMG) is not None
    r = df.roi(r)  # get the ROI out again
    assert r.get(Datum.ROI).bb() == Rect(2, 2, 3, 4)
