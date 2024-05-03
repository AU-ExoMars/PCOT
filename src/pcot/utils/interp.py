"""
Trilinear interpolation of a 3D array.

Code from https://stackoverflow.com/questions/21836067/interpolate-3d-volume-with-numpy-and-or-scipy
answer by Pietro D'Antuono https://stackoverflow.com/a/64595110
"""
from typing import Union

import numpy as np
from itertools import product


def searchsorted(ll, x):
    """
    searchsorted returns the index of the first value in the array that is greater than or equal to the input
    or -1 if not found.
    Oddly this seems quicker than numpy's searchsorted a lot of the time.
    """
    left, right = 0, len(ll)
    while left < right:
        mid = (left + right) // 2
        if ll[mid] < x:
            left = mid + 1
        else:
            right = mid
    return right if right < len(ll) else -1


def trilinear_interpolation_fast(x_volume: Union[list, np.ndarray],
                                 y_volume: Union[list, np.ndarray],
                                 z_volume: Union[list, np.ndarray],
                                 volume: np.ndarray,
                                 x_needed: float, y_needed: float, z_needed: float) -> float:
    """
    Trilinear interpolation. This version omits a lot of checks.

    :param x_volume: x points of the volume grid
    :param y_volume: y points of the volume grid
    :param z_volume: z points of the volume grid
    :param volume:   volume
    :param x_needed: desired x coordinate of volume
    :param y_needed: desired y coordinate of volume
    :param z_needed: desired z coordinate of volume

    :return volume_needed: desired value of the volume, i.e. volume(x_needed, y_needed, z_needed)
    :type volume_needed: float
    """

    # get indices needed for the correct control volume definition
    i = searchsorted(x_volume, x_needed)
    j = searchsorted(y_volume, y_needed)
    k = searchsorted(z_volume, z_needed)
    # control volume definition
    control_volume_coordinates = np.array(
        [[x_volume[i - 1], y_volume[j - 1], z_volume[k - 1]], [x_volume[i], y_volume[j], z_volume[k]]])
    xd = (np.array([x_needed, y_needed, z_needed]) - control_volume_coordinates[0]) / (
            control_volume_coordinates[1] - control_volume_coordinates[0])
    # interpolation along x
    c2 = [[0, 0], [0, 0]]
    for m, n in product([0, 1], [0, 1]):
        c2[m][n] = volume[i - 1][j - 1 + m][k - 1 + n] * (1 - xd[0]) + volume[i][j - 1 + m][k - 1 + n] * xd[0]
    # interpolation along y
    c1 = [0, 0]
    c1[0] = c2[0][0] * (1 - xd[1]) + c2[1][0] * xd[1]
    c1[1] = c2[0][1] * (1 - xd[1]) + c2[1][1] * xd[1]
    # interpolation along z
    volume_needed = c1[0] * (1 - xd[2]) + c1[1] * xd[2]
    return volume_needed


def trilinear_interpolation(x_volume: Union[list, np.ndarray],
                            y_volume: Union[list, np.ndarray],
                            z_volume: Union[list, np.ndarray],
                            volume: np.ndarray,
                            x_needed: float, y_needed: float, z_needed: float) -> float:
    """
    Trilinear interpolation (from Wikipedia)

    :param x_volume: x points of the volume grid
    :param y_volume: y points of the volume grid
    :param z_volume: z points of the volume grid
    :param volume:   volume
    :param x_needed: desired x coordinate of volume
    :param y_needed: desired y coordinate of volume
    :param z_needed: desired z coordinate of volume

    :return volume_needed: desired value of the volume, i.e. volume(x_needed, y_needed, z_needed)
    :type volume_needed: float
    """

    # test that the coordinates are in monotonically increasing order
    if not np.all(np.diff(x_volume) > 0):
        raise ValueError('x_volume is not in increasing order')
    if not np.all(np.diff(y_volume) > 0):
        raise ValueError('y_volume is not in increasing order')
    if not np.all(np.diff(z_volume) > 0):
        raise ValueError('z_volume is not in increasing order')

    # clip the coordinates to the limits
    x_needed = np.clip(x_needed, x_volume[0], x_volume[-1])
    y_needed = np.clip(y_needed, y_volume[0], y_volume[-1])
    z_needed = np.clip(z_needed, z_volume[0], z_volume[-1])

    # dimension check
    if np.shape(volume) != (len(x_volume), len(y_volume), len(z_volume)):
        raise ValueError(
            f'dimension mismatch, volume must be a ({len(x_volume)}, {len(y_volume)}, {len(z_volume)}) list or numpy.ndarray')
    # get indices needed for the correct control volume definition
    i = searchsorted(x_volume, x_needed)
    j = searchsorted(y_volume, y_needed)
    k = searchsorted(z_volume, z_needed)
    # control volume definition
    control_volume_coordinates = np.array(
        [[x_volume[i - 1], y_volume[j - 1], z_volume[k - 1]], [x_volume[i], y_volume[j], z_volume[k]]])
    xd = (np.array([x_needed, y_needed, z_needed]) - control_volume_coordinates[0]) / (
            control_volume_coordinates[1] - control_volume_coordinates[0])
    # interpolation along x
    c2 = [[0, 0], [0, 0]]
    for m, n in product([0, 1], [0, 1]):
        c2[m][n] = volume[i - 1][j - 1 + m][k - 1 + n] * (1 - xd[0]) + volume[i][j - 1 + m][k - 1 + n] * xd[0]
    # interpolation along y
    c1 = [0, 0]
    c1[0] = c2[0][0] * (1 - xd[1]) + c2[1][0] * xd[1]
    c1[1] = c2[0][1] * (1 - xd[1]) + c2[1][1] * xd[1]
    # interpolation along z
    volume_needed = c1[0] * (1 - xd[2]) + c1[1] * xd[2]
    return volume_needed
