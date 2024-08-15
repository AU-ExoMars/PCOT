"""the ENVI file input method, only supports 32 bit float, non-interleaved"""
import logging
from typing import Optional

from pcot.dataformats import load
from pcot.datum import Datum
from pcot.inputs.inputmethod import InputMethod
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import TreeMethodWidget


logger = logging.getLogger(__name__)


class ENVIInputMethod(InputMethod):
    img: Optional[Datum]
    fname: Optional[str]
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None     # this is the datum of the loaded image, or None.
        self.fname = None
        self.mapping = ChannelMapping()

    def loadImg(self):
        logger.debug("PERFORMING FILE READ")
        # try to load the image.
        self.img = load.envi(self.fname, self.input.idx if self.input else None, self.mapping)
        logger.info(f"------------ Image {self.fname} loaded: {self.img}, mapping is {self.mapping}")

    def readData(self):
        # if the image is not loaded and the filename is set, then load it
        if self.img is None and self.fname is not None:
            self.loadImg()
        # if the image didn't load or there was no filename, return null
        if self.img is None:
            return Datum.null
        # otherwise, return the image
        return self.img

    def getName(self):
        return "ENVI"

    # used from external code
    def setFileName(self, fname) -> InputMethod:
        self.fname = fname
        self.mapping = ChannelMapping()
        return self

    def createWidget(self):
        return ENVIMethodWidget(self)

    def serialise(self, internal):
        x = {'fname': self.fname}
        if internal:
            x['image'] = self.img.get(Datum.IMG) if self.img is not None else None
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.fname = data['fname']
        if internal:
            self.img = ImageCube(data['image']) if data['image'] is not None else None
        else:
            self.img = None   # ensure image is reloaded
        Canvas.deserialise(self, data)


class ENVIMethodWidget(TreeMethodWidget):
    def __init__(self, m):
        super().__init__(m, 'inputfiletree.ui', ["*.hdr"])

    def onInputChanged(self):
        # ensure image is also using my mapping, if it's an image
        logger.debug("ENVI onInputChanged")

        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
        d = self.method.get()
        if d is None or d.isNone():   # if we can't get a datum, or the datum is null, return
            return
        img = d.get(Datum.IMG)
        if img is not None:
            img.setMapping(self.method.mapping)
            logger.info(f"Displaying image {img}, mapping {self.method.mapping}")
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.method.input.performGraph()
        self.canvas.display(d)
        logger.debug("ENVI onInputChanged complete")

