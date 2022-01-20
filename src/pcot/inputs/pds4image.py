import os
from typing import Optional

from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import Qt

import pcot
import pcot.ui as ui
from pcot.inputs.inputmethod import InputMethod
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from pcot.ui.linear import LinearSetEntity, entityMarkerInitSetup, entityMarkerPaintSetup, TickRenderer


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
            self.img = None  # ensure image is reloaded
        Canvas.deserialise(self, data)

    def long(self):
        return f"ENVI:{self.fname}"


class ExampleMarkerItem(QtWidgets.QGraphicsRectItem):
    """This is an example marker item which is a cyan rectangle - other than that it's the
    same as the standard kind."""

    def __init__(self, x, y, ent, radius=10):
        super().__init__(x - radius / 2, y - radius / 2, radius, radius)
        entityMarkerInitSetup(self, ent)
        self.unselCol = Qt.cyan

    def paint(self, painter, option, widget):
        """and draw."""
        entityMarkerPaintSetup(self, option, self.unselCol, self.selCol)
        super().paint(painter, option, widget)


class ExampleLinearSetEntityA(LinearSetEntity):
    """This is an entity which uses the above example marker item"""

    def createMarkerItem(self, x, y):
        return ExampleMarkerItem(x, y, self)


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

        # create some tick renderers for the widget
        # this is for big text when the ticks are far apart
        self.timeline.addTickRenderer(TickRenderer(spacing=1, fontsize=20, textcol=(0, 0, 255), minxdist=50,
                                                   textgenfunc=lambda x: f"sol {int(x)}"))
        # this is the same, but the text is smaller and renders when the ticks are close together
        self.timeline.addTickRenderer(TickRenderer(spacing=1, fontsize=10, textcol=(0, 0, 255), maxxdist=50,
                                                   textgenfunc=lambda x: f"{int(x)}"))

        # and these are intermediate values
        self.timeline.addTickRenderer(
            TickRenderer(spacing=0.1, fontsize=8, textoffset=30, linecol=(230, 230, 230), linelen=0.5, minxdist=10,
                         textgenfunc=lambda x: f"{int(x*10+0.3)%10}", textalways=True))
        self.timeline.setYOffset(100)   # make room for axis text

        # add some test data to the linear widget
        items = []
        for day in range(10):
            xx = [LinearSetEntity(day, i, f"filt{i}", None) for i in range(10)]
            items += xx
            items.append(ExampleLinearSetEntityA(day + 0.5, 12, "foon", None))
        self.timeline.setItems(items)
        self.timeline.rescale()
        self.timeline.rebuild()

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
