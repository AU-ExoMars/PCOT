## the RGB file input method
import logging
from typing import Optional

import pcot.config
from pcot.imagecube import ChannelMapping, VALID_RASTER_FORMATS
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import TreeMethodWidget
from .inputmethod import InputMethod
from ..dataformats import load
from ..datum import Datum
from ..parameters.taggedaggregates import TaggedDict

logger = logging.getLogger(__name__)


DEBAYER_PATTERNS = ["GB","BG","GR","RG"]
DEBAYER_ALGOS = ["BILINEAR","EA","VNG","NONE"]


class RGBInputMethod(InputMethod):
    img: Optional[Datum]
    fname: Optional[str]
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.fname = None
        self.img = None         # we keep this around to speed up internal ser/deser
        self.mapping = ChannelMapping()
        self.debayer_algo = "NONE"
        self.debayer_pattern = pcot.config.defaultBayerPattern
        self.camera = "NONE"

    def readData(self):
        logger.debug(f"RGB readData fname={self.fname}")
        if self.fname is not None:
            self.img = load.rgb(self.fname,
                                self.input.idx if self.input else None,
                                self.mapping,
                                self.debayer_algo, self.debayer_pattern, None if self.camera=="NONE" else self.camera)
        else:
            self.img = Datum.null
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
        x = {'fname': self.fname,
             'debayer-algo': self.debayer_algo, 'debayer-pattern': self.debayer_pattern,
             'camera' : self.camera
             }
        if internal:
            x['image'] = self.img.get(Datum.IMG) if self.img is not None else None
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.fname = data['fname']
        self.debayer_algo = data.get('debayer-algo', 'NONE')
        self.debayer_pattern = data.get('debayer-pattern', 'GB')
        self.camera = data.get("camera", "NONE")
        if internal:
            x = data['image']
            self.img = Datum(Datum.IMG, x) if x is not None else None
        else:
            self.img = None   # ensure image is reloaded
        Canvas.deserialise(self, data)

    def modifyWithParameterDict(self, d: TaggedDict) -> bool:
        if d.rgb.filename is not None:
            # the filename being present means we have modified - the other two entries
            # are irrelevant from that point of view; we always return true.
            self.fname = d.rgb.filename
            if d.rgb.debayer_algo is not None:
                self.debayer_algo = d.rgb.debayer_algo.upper()
            if d.rgb.debayer_pattern is not None:
                self.debayer_pattern = d.rgb.debayer_pattern.upper()
            if d.rgb.camera is not None:
                self.camera = d.rgb.camera
            return True
        return False


class RGBMethodWidget(TreeMethodWidget):
    def __init__(self, m):
        super().__init__(m, 'inputrgb.ui',
                         [f"*.{x}" for x in VALID_RASTER_FORMATS])
        self.treeView.setMinimumSize(300, 400)
        self.treeView.setMaximumHeight(700)

        self.patternCombo.addItems(DEBAYER_PATTERNS)
        self.algoCombo.addItems(DEBAYER_ALGOS)
        from ..cameras import getCameraNames
        self.cameraCombo.addItem("NONE")
        self.cameraCombo.addItems(getCameraNames())

        self.patternCombo.currentIndexChanged.connect(self.patternChanged)
        self.algoCombo.currentIndexChanged.connect(self.algoChanged)
        self.cameraCombo.currentTextChanged.connect(self.cameraChanged)


        self.onInputChanged()

    def onInputChanged(self):
        self.patternCombo.setCurrentText(self.method.debayer_pattern)
        self.algoCombo.setCurrentText(self.method.debayer_algo)
        self.cameraCombo.setCurrentText(self.method.camera)

        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
            self.method.input.performGraph()
        self.canvas.display(self.method.get())

    def patternChanged(self, i):
        self.method.debayer_pattern = self.patternCombo.currentText()
        self.onInputChanged()

    def algoChanged(self, i):
        self.method.debayer_algo = self.algoCombo.currentText()
        self.onInputChanged()

    def cameraChanged(self, text):
        from pcot import ui
        self.method.camera = text
        ui.log(f"CAM {text}")
        self.onInputChanged()




