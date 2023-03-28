import numpy as np
import pcot
from pcot.imagecube import ImageCube
import pytest

def test_2dimage():
    """Test a 2D image is OK"""
    a = np.full((20,20),1).astype(np.float32)
    assert ImageCube(a).channels == 1
    
def test_degenerate2dimage():
    """Should also be possible to create a 2D image from a 3D image with 1 band"""
    a = np.full((20,20,1),1).astype(np.float32)
    img = ImageCube(a)
    assert img.img.shape == (20,20)
    assert img.channels == 1
    
def test_3dimage():
    """Test a 3D image is OK"""
    a = np.full((20,20,4),1).astype(np.float32)
    assert ImageCube(a).channels == 4

def test_badshape():
    """A 4D image is right out"""
    a = np.full((20,20,4,4),1).astype(np.float32)
    with pytest.raises(Exception) as info:
        ImageCube(a)
    assert "must be 3-dimensional" in str(info.value)
    
