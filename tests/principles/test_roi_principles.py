import pytest


def test_roi_single_image():
    """Test that a single 'standard operation' - one which uses modifyWithSub - works
    correctly on an image with a single ROI. ROIs and modifyWithSub are tested at a lower
    level in basic/test_roi.py; this tests that the layers above use the right code."""
