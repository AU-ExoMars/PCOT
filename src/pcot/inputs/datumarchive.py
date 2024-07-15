"""
The input method for Datum archives (items saved using the DatumStore/FileArchive
mechanism). These should have a MANIFEST file.
"""
import logging
from typing import Optional, Tuple, Dict

from pcot.datum import Datum
from pcot.imagecube import ChannelMapping
from pcot.inputs.inputmethod import InputMethod
from pcot.ui import uiloader
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from pcot.utils.archive import FileArchive
from pcot.utils.datumstore import DatumStore

logger = logging.getLogger(__name__)


class DatumArchiveInputMethod(InputMethod):
    datum: Optional[Datum]
    fname: Optional[str]
    itemname: Optional[str]
    manifest: Dict[str, Tuple[str, str, str]]
    mapping: ChannelMapping

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None
        self.fname = None
        self.itemname = None
        self.datum = None
        self.manifest = {}
        self.mapping = ChannelMapping()

    def loadManifest(self):
        if self.fname is not None:
            a = DatumStore(FileArchive(self.fname))
            self.manifest = a.manifest
        else:
            self.manifest = {}

    def readData(self):
        if self.fname is not None and self.itemname is not None:
            a = DatumStore(FileArchive(self.fname))
            self.datum = a.get(self.itemname, self._document())
        else:
            self.datum = None

    def getName(self):
        return "DatumArchive"

    def serialise(self, internal):
        x = {'fname': self.fname, 'itemname': self.itemname}
        if internal:
            x['datum'] = self.datum.serialise() if self.datum is not None else None
        Canvas.serialise(self, x)

    def deserialise(self, data, internal):
        self.fname = data['fname']
        self.itemname = data['itemname']
        if internal and data['datum'] is not None:
            self.datum = Datum.deserialise(data['datum'], self._document())
        else:
            self.datum = None
        Canvas.deserialise(self, data)

    def createWidget(self):
        return DatumArchiveMethodWidget(self)


class DatumArchiveMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        uiloader.loadUi("inputdatum.ui", self)
        self.openButton.clicked.connect(self.openFile)
        self.itemList.doubleClicked.connect(self.itemSelected)

        self.data.canvas.setMapping(m.mapping)
        # the canvas gets its "caption display" setting from the graph, so
        # we need to get it from the document, which is stored in the manager,
        # which we get from the input, which we get from the method. Ugh.
        # Indirection, eh?
        self.data.canvas.setGraph(m.input.mgr.doc.graph)
        self.data.canvas.setPersister(m)

        self.onInputChanged()

    def onInputChanged(self):
        pass

    def openFile(self):
        pass

    def itemSelected(self):
        pass
