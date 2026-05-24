"""
Bayer CFA Masks
===============

*Bayer* CFA (Colour Filter Array) masks generation.
"""

import typing

import numpy as np

__author__ = "Colour Developers"
__copyright__ = "Copyright 2015 Colour Developers"
__license__ = "BSD-3-Clause - https://opensource.org/licenses/BSD-3-Clause"
__maintainer__ = "Colour Developers"
__email__ = "colour-developers@colour-science.org"
__status__ = "Production"

__all__ = [
    "masks_CFA_Bayer",
]


# these three methods come from the colour-science package and have been rather truncated.

def as_float_array(a):
    return np.array(a).astype(np.float32)

def tstack(a):
    return np.concatenate([x[..., np.newaxis] for x in a], axis=-1)

def tsplit(a):
    return np.array([a[..., x] for x in range(a.shape[-1])])


def masks_CFA_Bayer(
    shape: int | typing.Tuple[int, ...],
    pattern: typing.Literal["RGGB", "BGGR", "GRBG", "GBRG"] | str = "RGGB",
) -> typing.Tuple[np.ndarray, ...]:
    """
    Return the *Bayer* CFA red, green and blue masks for given pattern.

    Parameters
    ----------
    shape
        Dimensions of the *Bayer* CFA.
    pattern
        Arrangement of the colour filters on the pixel array.

    Returns
    -------
    :class:`tuple`
        *Bayer* CFA red, green and blue masks.

    Examples
    --------
    >>> from pprint import pprint
    >>> shape = (3, 3)
    >>> pprint(masks_CFA_Bayer(shape))
    (array([[ True, False,  True],
           [False, False, False],
           [ True, False,  True]], dtype=bool),
     array([[False,  True, False],
           [ True, False,  True],
           [False,  True, False]], dtype=bool),
     array([[False, False, False],
           [False,  True, False],
           [False, False, False]], dtype=bool))
    >>> pprint(masks_CFA_Bayer(shape, "BGGR"))
    (array([[False, False, False],
           [False,  True, False],
           [False, False, False]], dtype=bool),
     array([[False,  True, False],
           [ True, False,  True],
           [False,  True, False]], dtype=bool),
     array([[ True, False,  True],
           [False, False, False],
           [ True, False,  True]], dtype=bool))
    """

    channels = {channel: np.zeros(shape, dtype="bool") for channel in "RGB"}
    for channel, (y, x) in zip(pattern, [(0, 0), (0, 1), (1, 0), (1, 1)], strict=False):
        channels[channel][y::2, x::2] = 1

    return tuple(channels.values())