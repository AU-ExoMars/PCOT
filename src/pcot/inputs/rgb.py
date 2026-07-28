## the RGB file input method
import logging
import os
from typing import Optional

import pcot.config
from pcot.imagecube import ChannelMapping, VALID_RASTER_FORMATS
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import TreeMethodWidget
from .inputmethod import InputMethod
from ..dataformats import load
from ..datum import Datum
from ..parameters.taggedaggregates import TaggedDict
from ..utils.demosaicing import DEBAYER_ALGOS, NEGATIVE_PROCESSING_METHODS, VALID_BAYER_PATTERNS

logger = logging.getLogger(__name__)


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
        self.debayer_pattern = pcot.config.data.defaultbayerpattern
        self.camera = "NONE"
        self.neg_method = "Leave"
        # whether readData() has actually run this session - False for a document just loaded from
        # a .pcot file, where the image data is cached and the file hasn't really been re-read. Used
        # to distinguish "(cached)" from "(failed)" in the widget when dnRange isn't available.
        self.dnRangeAttempted = False

    def readData(self):
        logger.debug(f"RGB readData fname={self.fname}")
        self.dnRangeAttempted = True
        if self.debayer_pattern is None:
            print("no debayer pat")
        if self.fname is not None:
            self.img = load.rgb(self.fname,
                                self.input.idx if self.input else None,
                                self.mapping,
                                self.debayer_algo, self.debayer_pattern, None if self.camera=="NONE" else self.camera,
                                self.neg_method)
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

    def missingPathReason(self) -> Optional[str]:
        if self.fname is not None and not os.path.isfile(self.fname):
            return f"File not found: {self.fname}{self._cachedDataSuffix()}"
        return None

    # We actually serialise and deserialise the imagecube, not the containing datum.

    def serialise(self, internal):
        x = {'fname': self.fname,
             'debayer-algo': self.debayer_algo, 'debayer-pattern': self.debayer_pattern,
             'camera' : self.camera,
             "neg_method": self.neg_method
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
        self.neg_method = data.get('neg_method', NEGATIVE_PROCESSING_METHODS[0])
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
            if d.rgb.neg_method is not None:
                self.neg_method = d.rgb.neg_method
            return True
        return False


class RGBMethodWidget(TreeMethodWidget):
    def __init__(self, m):
        super().__init__(m, 'inputrgb.ui',
                         [f"*.{x}" for x in VALID_RASTER_FORMATS])
        self.treeView.setMinimumSize(300, 400)
        self.treeView.setMaximumHeight(700)

        self.patternCombo.addItems(VALID_BAYER_PATTERNS)
        self.algoCombo.addItems(DEBAYER_ALGOS)
        self.negCombo.addItems(NEGATIVE_PROCESSING_METHODS)
        from ..cameras import getCameraNames
        self.cameraCombo.addItem("NONE")
        self.cameraCombo.addItems(getCameraNames())

        self.patternCombo.currentIndexChanged.connect(self.patternChanged)
        self.algoCombo.currentIndexChanged.connect(self.algoChanged)
        self.cameraCombo.currentTextChanged.connect(self.cameraChanged)
        self.negCombo.currentTextChanged.connect(self.negChanged)


        self.syncIfActive()

    def onInputChanged(self):
        self.patternCombo.setCurrentText(self.method.debayer_pattern)
        self.algoCombo.setCurrentText(self.method.debayer_algo)
        self.cameraCombo.setCurrentText(self.method.camera)
        self.negCombo.setCurrentText(self.method.neg_method)

        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
            self.method.input.performGraph()

        datum = self.method.get()
        self.canvas.display(datum)

        cube = datum.get(Datum.IMG)
        if cube is not None and cube.dnRange is not None:
            mn, mx = cube.dnRange
            self.dnRangeLabel.setText(f"DN range in file: [{mn:g}, {mx:g}]")
        elif self.method.fname is None:
            self.dnRangeLabel.setText("DN range in file: n/a")
        elif not self.method.dnRangeAttempted:
            self.dnRangeLabel.setText("DN range in file: (cached)")
        else:
            self.dnRangeLabel.setText("DN range in file: (failed)")

    def patternChanged(self, i):
        self.method.debayer_pattern = self.patternCombo.currentText()
        self.onInputChanged()

    def algoChanged(self, i):
        self.method.debayer_algo = self.algoCombo.currentText()
        self.onInputChanged()

    def negChanged(self, i):
        self.method.neg_method = self.negCombo.currentText()
        self.onInputChanged()

    def cameraChanged(self, text):
        from pcot import ui
        self.method.camera = text
        ui.log(f"CAM {text}")
        self.onInputChanged()
