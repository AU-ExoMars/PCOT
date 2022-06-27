"""It's quite difficult to test ROIs, but we'll try to at least do rect and poly"""
from fixtures import *
from pcot.rois import ROIRect, ROIBoundsException
from pcot.utils.geom import Rect


def test_nonintersecting_roi(allblack):
    """Check that trying to get the subimage for an ROI which doesn't intersect
    the image throws an exception"""
    roi = ROIRect()
    roi.setBB(20, 20, 10, 10)
    allblack.rois.append(roi)

    with pytest.raises(ROIBoundsException):
        allblack.subimage()


def test_nonintersecting_negative_roi(allblack):
    """As above, but the ROI starts at negative coords"""
    roi = ROIRect()
    roi.setBB(-20, -20, 10, 10)
    allblack.rois.append(roi)

    with pytest.raises(ROIBoundsException):
        allblack.subimage()


def test_rect_clipped(allblack):
    """Test a rect ROI that gets clipped to the bottom-right of the image (i.e. ROI is too big)"""
    roi = ROIRect()
    roi.setBB(2, 2, 10, 10)
    allblack.rois.append(roi)

    subimg = allblack.subimage()
    assert subimg.bb == Rect(2, 2, 10, 6)   # will be clipped (ROI bigger than image)

