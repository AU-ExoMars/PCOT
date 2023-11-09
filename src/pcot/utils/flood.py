from dataclasses import dataclass

import numpy as np

from pcot.rois import ROIPainted


@dataclass
class FloodFillParams:
    # minpix and maxpix are the minimum and maximum number of pixels to fill. If the fill is outside these bounds,
    # None is returned.
    minpix: int = 0
    maxpix: int = 10000
    # threshold is the threshold for the fill. What it actually means depends on the fill update method,
    # which typically involves a running mean or a running variance/SD.
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

        # build a 1D view of the image
        self.img = self.img.ravel()
        self.size = self.h * self.w       # the size of the one-dimensional view of the array

        # build a 1D mask for the image
        self.mask = np.zeros(self.size, dtype=np.bool)

        self.n = 0
        self.params = params
        # break this out for speed
        self.threshold = params.threshold

    def unravel(self):
        """Convert the mask to a 2D array"""
        return self.mask.reshape(self.h, self.w)

    def fill(self, x, y) -> np.ndarray:
        """Perform the fill, returning true if the number of pixels found
        was within an acceptable range (will exit early if too many). Returns a mask or None
        if the filled pixels were too few or too many"""
        pass

    def fillToPaintedRegion(self, x, y):
        """As fill(), but returns an ROIPainted object instead of a mask"""
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
        self.means = 0

    def fill(self, x, y):
        # get the address of the pixel we're starting from in the 1D array, assuming it's in column-major order
        # (which it is)
        stack = [x + y * self.w]
        maxpix = self.params.maxpix
        while stack:
            addr = stack.pop()
            if addr < 0 or addr >= self.size:
                # outside image, must be outside the fill
                continue
            if self.mask[addr]:
                # already filled
                continue
            # get the point we're talking about in the image
            # and see how far it is from the running mean
            if self.n > 0:
                dsq = (self.img[addr] - self.means) ** 2
                if dsq > self.threshold:
                    continue
                if self.n > maxpix:
                    return None
            if not self.mask[addr]:
                self.mask[addr] = True
                self.means = (self.img[addr] + self.n * self.means) / (self.n + 1)
                self.n += 1
                stack.append(addr - 1)
                stack.append(addr + 1)
                stack.append(addr - self.w)
                stack.append(addr + self.w)
        if self.n < self.params.minpix:
            return None
        else:
            return self.unravel()
