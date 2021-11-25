import os
from typing import Optional

from PyQt5 import uic, QtWidgets
from PyQt5.QtWidgets import QDialog

import pcot
import pcot.ui as ui
from pcot.inputs.inputmethod import InputMethod
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget


class PDS4ImageInputMethod(InputMethod):
    img: Optional[ImageCube]
    fname: Optional[str]
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None
        self.fname = None
        self.mapping = ChannelMapping()

    def loadImg(self):
        print("PDS4IMAGE PERFORMING FILE READ")
        img = None
        ui.log("Image {} loaded: {}, mapping is {}".format(self.fname, img, self.mapping))
        self.img = img

    def readData(self):
        if self.img is None and self.fname is not None:
            self.loadImg()
        return self.img

    def getName(self):
        return "PDS4"

    # used from external code
    def setFileName(self, fname):
        self.fname = fname
        self.mapping = ChannelMapping()

    def createWidget(self):
        return PDS4ImageMethodWidget(self)

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

    def long(self):
        return f"ENVI:{self.fname}"


class PDS4ImageMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        uic.loadUi(pcot.config.getAssetAsFile('inputpdsfile.ui'), self)

        d = pcot.config.getDefaultDir('images')
        self.dir = None
        if d is not None and d != '':
            self.selectDir(d)
        else:
            self.selectDir('.')

        self.browse.clicked.connect(self.onBrowse)

        # add some test data to the linear widget
        timeline = self.timeline
        for i in range(10):
            timeline.add(i, f"wibble{i}")
        timeline.rescale()
        timeline.rebuild()

    def selectDir(self, d):
        self.dir = d
        self.fileEdit.setText(d)
        # and find the files...

    def onBrowse(self):
        res = QtWidgets.QFileDialog.getExistingDirectory(None, 'Directory for products',
                                                         os.path.expanduser(self.dir))
        if res != '':
            self.selectDir(res)

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

