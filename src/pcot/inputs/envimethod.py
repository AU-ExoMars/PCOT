"""the ENVI file input method, only supports 32 bit float, non-interleaved"""
import os
from typing import Optional

import pcot
import pcot.envi as envi
import pcot.ui as ui
from pcot.inputs.inputmethod import InputMethod
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import TreeMethodWidget


class ENVIInputMethod(InputMethod):
    img: Optional[ImageCube]
    fname: Optional[str]
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None
        self.fname = None
        self.mapping = ChannelMapping()

    def loadImg(self):
        print("ENVI PERFORMING FILE READ")
        img = envi.load(self.fname, self.mapping)
        ui.log("Image {} loaded: {}, mapping is {}".format(self.fname, img, self.mapping))
        self.img = img

    def readData(self):
        if self.img is None and self.fname is not None:
            self.loadImg()
        return self.img

    def getName(self):
        return "ENVI"

    # used from external code
    def setFileName(self, fname):
        self.fname = fname
        self.mapping = ChannelMapping()

    def createWidget(self):
        return ENVIMethodWidget(self)

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

    def brief(self):
        return self.fname


class ENVIMethodWidget(TreeMethodWidget):
    def __init__(self, m):
        super().__init__(m, 'tabrgbfile.ui', ["*.hdr"])

    def onInputChanged(self):
        # ensure image is also using my mapping.
        if self.method.img is not None:
            self.method.img.setMapping(self.method.mapping)
        print("Displaying image {}, mapping {}".format(self.method.img, self.method.mapping))
        self.invalidate()  # input has changed, invalidate so the cache is dirtied
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.method.input.performGraph()
        self.canvas.display(self.method.img)

