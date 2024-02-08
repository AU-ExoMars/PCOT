## the RGB file input method
import logging
from typing import Optional

import pcot.ui as ui
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import TreeMethodWidget
from .inputmethod import InputMethod
from ..datum import Datum
from ..sources import MultiBandSource, Source, StringExternal

logger = logging.getLogger(__name__)


class RGBInputMethod(InputMethod):
    img: Optional[ImageCube]
    fname: Optional[str]
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None
        self.fname = None
        self.mapping = ChannelMapping()

    def loadImg(self):
        # will throw exception if load failed
        logger.info("RGB PERFORMING FILE READ")

        # might seem a bit wasteful having three of them, but seems more logical to me.
        e = StringExternal("RGB", self.fname)
        sources = MultiBandSource([
            Source().setBand("R").setExternal(e).setInputIdx(self.input.idx),
            Source().setBand("G").setExternal(e).setInputIdx(self.input.idx),
            Source().setBand("B").setExternal(e).setInputIdx(self.input.idx),
        ])

        img = ImageCube.load(self.fname, self.mapping, sources)
        ui.log("Image {} loaded: {}".format(self.fname, img))
        self.img = img

    def readData(self):
        if self.img is None and self.fname is not None:
            self.loadImg()
        return Datum(Datum.IMG, self.img)

    def getName(self):
        return "RGB"

    # used from external code
    def setFileName(self, fname):
        self.fname = fname
        self.mapping = ChannelMapping()
        return self

    def createWidget(self):
        return RGBMethodWidget(self)

    def serialise(self, internal):
        x = {'fname': self.fname}
        if internal:
            x['image'] = self.img
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.fname = data['fname']
        if internal:
            self.img = data['image']
        else:
            self.img = None   # ensure image is reloaded
        Canvas.deserialise(self, data)



class RGBMethodWidget(TreeMethodWidget):
    def __init__(self, m):
        super().__init__(m, 'inputfiletree.ui',
                         ["*.jpg", "*.png", "*.ppm", "*.tga", "*.tif"])

    def onInputChanged(self):
        self.invalidate()  # input has changed, invalidate so the cache is dirtied
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.method.input.performGraph()
        self.canvas.display(self.method.img)




