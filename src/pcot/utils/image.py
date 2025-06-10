import numpy as np

"""Various low-level image utilities"""


def imgsplit(img):
    """Does the same as cv.split, effectively, but is guaranteed to work on >3 channels. Who knows if CV will
    always do that. Will also split a single band image into a single channel."""
    if img.ndim == 2:
        # single band image, return as a list with one element
        return [img]
    return [np.reshape(x, img.shape[:2]) for x in np.dsplit(img, img.shape[-1])]


def imgmerge(img):
    """Trivial, but goes with imgsplit"""
    return np.dstack(img)


def generate_gradient(w, h, is_horizontal, steps=0, start=0, stop=1):
    """Generates a gradient image of size (w, h) with values ranging from start to stop. If is_horizontal is True,
    the gradient will be horizontal, otherwise vertical. If steps is > 0, the gradient will be quantized to that
    number of steps."""

    def quantize(input_array, num_steps):
        # Generate bin edges
        bin_edges = np.linspace(0, 1, int(num_steps) + 1)
        # Quantize the array
        quantized_array = np.digitize(input_array, bin_edges, right=True) - 1
        # Adjust values to be in the range [0, num_steps-1]
        quantized_array = np.clip(quantized_array, 0, num_steps - 1)
        # divide down to the range [0, 1]
        return quantized_array / (num_steps - 1)

    if is_horizontal:
        x = np.tile(np.linspace(start, stop, w), (h, 1)).astype(np.float32)
    else:
        x = np.tile(np.linspace(start, stop, h), (w, 1)).T.astype(np.float32)
    return quantize(x, steps) if steps > 0 else x
