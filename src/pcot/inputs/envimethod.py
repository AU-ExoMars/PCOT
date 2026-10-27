"""the ENVI file input method, only supports 32 bit float, non-interleaved"""
import logging
import os
from typing import Optional

from pcot.dataformats import load
from pcot.datum import Datum
from pcot.inputs.inputmethod import InputMethod
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.parameters.taggedaggregates import TaggedDict
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import TreeMethodWidget


logger = logging.getLogger(__name__)


class ENVIInputMethod(InputMethod):
    img: Optional[Datum]
    fname: Optional[str]
    mapping: ChannelMapping
    apply_gains_and_offsets: bool

    def __init__(self, inp):
        super().__init__(inp)
        self.fname = None
        self.img = None
        self.mapping = ChannelMapping()
        self.apply_gains_and_offsets = False

    def readData(self):
        # if the image is not loaded and the filename is set, then load it
        logger.debug(f"ENVI readData fname={self.fname}")
        if self.fname is None:
            self.img = Datum.null
        else:
            self.img = load.envi(self.fname, self.input.idx if self.input else None, self.mapping,
                                 self.apply_gains_and_offsets)
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

    def missingPathReason(self) -> Optional[str]:
        if self.fname is not None and not os.path.isfile(self.fname):
            return f"File not found: {self.fname}{self._cachedDataSuffix()}"
        return None

    def serialise(self, internal):
        x = {
            'fname': self.fname,
            'apply_gains_and_offsets': self.apply_gains_and_offsets
             }
        if internal:
            x['image'] = self.img.get(Datum.IMG) if self.img is not None else None
        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.fname = data['fname']
        self.apply_gains_and_offsets = data.get('apply_gains_and_offsets', False)
        if internal:
            self.img = ImageCube(data['image']) if data['image'] is not None else None
        else:
            self.img = None   # ensure image is reloaded
        Canvas.deserialise(self, data)

    def modifyWithParameterDict(self, d: TaggedDict) -> bool:
        e = d.envi
        if e.filename is not None:
            self.fname = e.filename
        elif e.apply_gains_and_offsets is None:
            return False    # nothing set for this method
        elif self.fname is None or not self.isActive():
            # setting the flag alone would otherwise select a stale or missing ENVI file
            raise Exception("envi.apply_gains_and_offsets set, but input is not already an ENVI file"
                            " and no envi.filename given")
        # if not set, keep the setting already in the document
        if e.apply_gains_and_offsets is not None:
            self.apply_gains_and_offsets = e.apply_gains_and_offsets
        return True


class ENVIMethodWidget(TreeMethodWidget):
    def __init__(self, m):
        super().__init__(m, 'inputenvi.ui', ["*.hdr"])
        self.gainsBox.setChecked(m.apply_gains_and_offsets)
        self.gainsBox.checkStateChanged.connect(self.gainsChanged)
        self.syncIfActive()

    def gainsChanged(self):
        self.method.apply_gains_and_offsets = self.gainsBox.isChecked()
        self.onInputChanged()

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
            logger.debug(f"Displaying image {img}, mapping {self.method.mapping}")
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.method.input.performGraph()
        self.canvas.display(d)
        logger.debug("ENVI onInputChanged complete")

