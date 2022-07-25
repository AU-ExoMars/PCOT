"""It's quite difficult to test ROIs, but we'll try to at least do rect and poly"""
from fixtures import *
from pcot.rois import ROIRect, ROIBoundsException, ROICircle
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
    assert subimg.bb == Rect(2, 2, 10, 6)  # will be clipped (ROI bigger than image)


def test_rect_clipped_topleft(allblack):
    """Now an ROI that's been clipped at top-left (i.e. xy -ve)"""

    roi = ROIRect()
    roi.setBB(-2, -5, 10, 10)
    allblack.rois.append(roi)

    subimg = allblack.subimage()
    assert subimg.bb == Rect(0, 0, 8, 5)


def test_rect_change(allblack):
    """Test that a rectangular ROI entirely within a black image, when modified, only changes the
    right number of pixels"""
    # make a boring ROI
    roi = ROIRect()
    roi.setBB(2, 2, 5, 5)
    allblack.rois.append(roi)
    subimg = allblack.subimage()
    assert subimg.bb == Rect(2, 2, 5, 5)

    # make a red full array of the right shape (I'll test masks separately)
    out = np.full(subimg.img.shape, [1, 0, 0]).astype(np.float32)
    # and now plug that back into the image, telling it which subimage we're modifying
    # and the output data.
    img = allblack.modifyWithSub(subimg, out)
    # and do some checks
    assert np.sum(img.img) == 25  # we're setting 5x5 to 1,0,0 - should sum to 25
    # make sure every cell is what it should be
    for x in range(16):
        for y in range(8):
            if (2 <= x < 7) and (2 <= y < 7):
                tst = (1, 0, 0)
            else:
                tst = (0, 0, 0)
            assert np.array_equal(img.img[y, x], tst)


def test_rect_change_red_to_cyan(allblack):
    """Test that a rectangular ROI entirely within a red image, when modified, only changes the
    right number of pixels to cyan"""
    # first, change the entire image to red.
    allblack.img[:] = (1, 0, 0)

    # make a boring ROI
    roi = ROIRect()
    roi.setBB(2, 2, 5, 5)
    allblack.rois.append(roi)
    subimg = allblack.subimage()
    assert subimg.bb == Rect(2, 2, 5, 5)

    # make a cyan array of the right shape (I'll test masks separately)
    out = np.full(subimg.img.shape, [0, 1, 1]).astype(np.float32)
    # and now plug that back into the image, telling it which subimage we're modifying
    # and the output data.
    img = allblack.modifyWithSub(subimg, out)
    # make sure every cell is what it should be
    for x in range(16):
        for y in range(8):
            if (2 <= x < 7) and (2 <= y < 7):
                tst = (0, 1, 1)
            else:
                tst = (1, 0, 0)
            assert np.array_equal(img.img[y, x], tst)


def test_circle_change_masked(allblack):
    """change a circle in black image to red, count red pixels."""
    # make a circular ROI
    roi = ROICircle(4, 4, 3)
    allblack.rois.append(roi)
    subimg = allblack.subimage()

    # make a red full array of the right shape (I'll test masks separately)
    out = np.full(subimg.img.shape, [1, 0, 0]).astype(np.float32)
    # and now plug that back into the image, telling it which subimage we're modifying
    # and the output data.
    img = allblack.modifyWithSub(subimg, out)
    # and do some checks. A radius 3 circle at low res is a bit crude - it's a 5x5 square
    # with single pixels sticking out of each side.
    assert np.sum(img.img) == 29


def test_circle_change_masked_red_to_cyan(allblack):
    """change a circle in a red image to cyan, count cyan pixels."""
    allblack.img[:] = (1, 0, 0)
    oldsum = np.sum(allblack.img)
    assert oldsum == allblack.w * allblack.h

    roi = ROICircle(4, 4, 3)
    allblack.rois.append(roi)
    subimg = allblack.subimage()

    out = np.full(subimg.img.shape, [0, 1, 1]).astype(np.float32)
    img = allblack.modifyWithSub(subimg, out)
    # now this time the number of set values should have gone up by 29 from whatever it was before, because
    # we are changing (1,0,0) to (0,1,1).
    assert np.sum(img.img) == oldsum + 29

    # and some arbitrary checks
    assert np.array_equal(img.img[1, 1], (1, 0, 0))
    assert np.array_equal(img.img[4, 4], (0, 1, 1))


def test_multi_roi_change(allblack):
    """Two circles within an image - we should change the union of those two circles"""

    allblack.rois.append(ROICircle(4, 4, 3))
    allblack.rois.append(ROICircle(12, 4, 3))
    subimg = allblack.subimage()
    out = np.full(subimg.img.shape, [0, 0, 1]).astype(np.float32)
    img = allblack.modifyWithSub(subimg, out)
    assert np.sum(img.img) ==  29*2
