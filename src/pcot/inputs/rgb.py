## the RGB file input method
import os
from typing import Optional

import pcot
import pcot.ui as ui
from pcot.inputs.inputmethod import InputMethod
from pcot.pancamimage import ImageCube, ChannelMapping
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import TreeMethodWidget


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
        print("RGB PERFORMING FILE READ")
        img = ImageCube.load(self.fname, self.mapping)
        ui.log("Image {} loaded: {}".format(self.fname, img))
        self.img = img

    def readData(self):
        if self.img is None and self.fname is not None:
            self.loadImg()
        return self.img

    def getName(self):
        return "RGB"

    # used from external code
    def setFileName(self, fname):
        self.fname = fname
        self.mapping = ChannelMapping()

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
        super().__init__(m, 'tabrgbfile.ui',
                         ["*.jpg", "*.png", "*.ppm", "*.tga", "*.tif"])

    def onInputChanged(self):
        self.invalidate()  # input has changed, invalidate so the cache is dirtied
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.method.input.performGraph()
        self.canvas.display(self.method.img)




