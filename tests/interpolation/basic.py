import numpy as np
import pytest

from pcot.utils.interp import trilinear_interpolation


def test_basic_trilinear_interpolation():
    x_volume = [0, 1, 2]
    y_volume = [0, 1, 2]
    z_volume = [0, 1, 2]
    # axes here - the innermost axis is the z axis, the middle axis is the y axis, and the outermost axis is the x axis
    # Thus x=0, y=1, z=2 gives point number 5
    volume = np.array([[[0, 1, 2], [3, 4, 5], [6, 7, 8]],
                       [[9, 10, 11], [12, 13, 14], [15, 16, 17]],
                       [[18, 19, 20], [21, 22, 23], [24, 25, 26]]])

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, 0, 0, 0)
    assert val == 0.0

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, 1, 1, 1)
    assert val == 13.0

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, 2, 2, 2)
    assert val == 26.0

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, 0, 1, 2)
    assert val == 5.0

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, 1.5, 1.5, 1.5)
    assert val == 19.5

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, 0, 1.5, 1.0)
    assert val == 5.5

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, 1.5, 0.5, 0.5)
    assert val == 15.5

    # test out of range
    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, -1, 1, 2)
    assert val == 5.0

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, -1, 1, 2.1)
    assert val == 5.0

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, 0, -2, 0)
    assert val == 0.0


def test_basic_trilinear_interpolation_irregular_axes():
    x_volume = np.array([0, 0.5, 1])
    y_volume = np.array([1, 2, 3])
    z_volume = np.array([0, 1, 2])
    # axes here - the innermost axis is the z axis, the middle axis is the y axis, and the outermost axis is the x axis
    # Thus x=0, y=1, z=2 gives point number 5
    volume = np.array([[[0, 1, 2], [3, 4, 5], [6, 7, 8]],
                       [[9, 10, 11], [12, 13, 14], [15, 16, 17]],
                       [[18, 19, 20], [21, 22, 23], [24, 25, 26]]])

    val = trilinear_interpolation(x_volume, y_volume, z_volume, volume, 1.5, 0.5, 0.5)
    assert val == 18.5


def test_bad_volumes():
    volume = np.array([[[0, 1, 2], [3, 4, 5], [6, 7, 8]],
                       [[9, 10, 11], [12, 13, 14], [15, 16, 17]],
                       [[18, 19, 20], [21, 22, 23], [24, 25, 26]]])

    x_volume = np.array([0, 0.5, 1])
    y_volume = np.array([1, 2, 1])
    z_volume = np.array([0, 1, 2])

    with pytest.raises(ValueError):
        trilinear_interpolation(x_volume, y_volume, z_volume, volume, 1.5, 0.5, 0.5)
