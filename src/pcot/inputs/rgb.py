## the RGB file input method
import logging
from typing import Optional

from pcot.imagecube import ChannelMapping
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import TreeMethodWidget
from .inputmethod import InputMethod
from ..dataformats import load
from ..datum import Datum
from ..parameters.taggedaggregates import TaggedDict

logger = logging.getLogger(__name__)


class RGBInputMethod(InputMethod):
    img: Optional[Datum]
    fname: Optional[str]
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.fname = None
        self.mapping = ChannelMapping()

    def readData(self):
        logger.debug(f"RGB readData fname={self.fname}")
        self.img = load.rgb(self.fname,
                            self.input.idx if self.input else None,
                            self.mapping)
        return self.img

    def getName(self):
        return "RGB"

    # used from external code
    def setFileName(self, fname):
        self.fname = fname
        self.mapping = ChannelMapping()
        return self

    def createWidget(self):
        return RGBMethodWidget(self)

    # We actually serialise and deserialise the imagecube, not the containing datum.

    def serialise(self, internal):
        x = {'fname': self.fname}
        if internal:
            x['image'] = self.img.get(Datum.IMG) if self.img is not None else None
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.fname = data['fname']
        if internal:
            x = data['image']
            self.img = Datum(Datum.IMG, x) if x is not None else None
        else:
            self.img = None   # ensure image is reloaded
        Canvas.deserialise(self, data)

    def modifyWithParameterDict(self, d: TaggedDict) -> bool:
        if d.rgb.filename is not None:
            self.fname = d.rgb.filename
            return True
        return False


class RGBMethodWidget(TreeMethodWidget):
    def __init__(self, m):
        super().__init__(m, 'inputfiletree.ui',
                         ["*.jpg", "*.png", "*.ppm", "*.tga", "*.tif"])

    def onInputChanged(self):
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
            self.method.input.performGraph()
        self.canvas.display(self.method.img)




