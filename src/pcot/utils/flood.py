from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class FloodFillParams:
    # minpix and maxpix are the minimum and maximum number of pixels to fill. If the fill is outside these bounds,
    # None is returned.
    minpix: int = 0
    maxpix: int = 10000
    # threshold is the threshold for the fill. What it actually means depends on the fill update method,
    # which typically involves a distance metric. For example, the FastFloodFill method uses a distance
    # from the seed point, and the threshold is the maximum distance to fill. The default value is 0.005,
    # which is very low.
    threshold: float = 0.005


class FloodFillerBase:
    """Base class for flood fillers. Subclasses should implement update() and inside(). The fill() method
    will return a mask if the number of pixels found is within the range minpix to maxpix, otherwise None.
    The fillToPaintedRegion() method will return an ROIPainted object instead of a mask.
    It's pretty ugly, because it would be better done functionally (using closures) but that gets messy."""

    def __init__(self, img, params=FloodFillParams()):
        # the first thing we need to do is to convert the image to a 2D array; that will speed things
        # up a lot. How we do this will depend on what channels we are interested in, but for now
        # we'll just take the mean of all channels.

        # find the mean of all channels in img.img
        if img.channels == 1:
            self.img = img.img
        else:
            self.img = np.mean(img.img, axis=2)
        self.h, self.w = self.img.shape
        self.params = params

    def fill(self, x, y) -> np.ndarray:
        """Perform the fill, returning true if the number of pixels found
        was within an acceptable range (will exit early if too many). Returns a mask or None
        if the filled pixels were too few or too many"""
        pass

    def fillToPaintedRegion(self, x, y):
        """As fill(), but returns an ROIPainted object instead of a mask"""
        from pcot.rois import ROIPainted

        mask = self.fill(x, y)
        if mask is None:
            return None
        roi = ROIPainted(mask=mask)
        # once we have generated the ROI, we need to set its dimensions
        roi.setContainingImageDimensions(self.w, self.h)
        # and crop it to the painted region
        roi.cropDownWithDraw()
        return roi


class MeanFloodFiller(FloodFillerBase):
    """Flood filler that uses a running mean to determine whether a pixel should be filled"""
    def __init__(self, img, params=FloodFillParams()):
        super().__init__(img, params)

    def fill(self, x, y):
        # get the address of the pixel we're starting from in the 1D array, assuming it's in column-major order
        # (which it is)

        # build a 1D view of the image
        img = self.img.ravel()
        means = 0
        n = 0
        w = self.w  # python doesn't do CSE
        size = self.h * w
        maxpix = self.params.maxpix
        threshold = self.params.threshold
        # build a 1D mask for the image - this will be the output
        mask = np.zeros(size, dtype=np.bool)

        queue = deque([x + y * w])
        while queue:
            addr = queue.popleft()
            if addr < 0 or addr >= size:
                # outside image, must be outside the fill
                continue
            if mask[addr]:
                # already filled
                continue
            # get the point we're talking about in the image
            # and see how far it is from the running mean
            if n > 0:
                dsq = (img[addr] - means) ** 2
                if dsq > threshold:
                    continue
                if n > maxpix:
                    return None
            if not mask[addr]:
                mask[addr] = True
                means = (img[addr] + n * means) / (n + 1)
                n += 1
                queue.append(addr - 1)
                queue.append(addr + 1)
                queue.append(addr - w)
                queue.append(addr + w)

        # main loop is done, now check the number of pixels filled
        if n < self.params.minpix:
            return None
        else:
            return mask.reshape((self.h, self.w))


class FastFloodFiller(FloodFillerBase):
    """This flood filler just uses the scikit-image flood fill algorithm. It's fast, but it doesn't
    do any checks on the number of pixels filled."""
    def __init__(self, img, params=FloodFillParams()):
        super().__init__(img, params)

    def fill(self, x, y):
        from skimage.segmentation import flood
        mask = flood(self.img, (y, x), tolerance=self.params.threshold)
        return mask
