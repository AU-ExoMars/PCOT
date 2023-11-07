import numpy as np

"""Various low-level image utilities"""


def imgsplit(img):
    """Does the same as cv.split, effectively, but is guaranteed to work on >3 channels. Who knows if CV will
    always do that."""
    return [np.reshape(x, img.shape[:2]) for x in np.dsplit(img, img.shape[-1])]


def imgmerge(img):
    """Trivial, but goes with imgsplit"""
    return np.dstack(img)


def generate_gradient(w, h, is_horizontal, start=0, stop=1):
    """Generates a gradient image of size (w, h) with values ranging from start to stop. If is_horizontal is True,
    the gradient will be horizontal, otherwise vertical."""
    if is_horizontal:
        return np.tile(np.linspace(start, stop, w), (h, 1)).astype(np.float32)
    else:
        return np.tile(np.linspace(start, stop, h), (w, 1)).T.astype(np.float32)
