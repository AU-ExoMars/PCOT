## the Multifile input method, inputting several greyscale images
# into a single image
import logging
import os
import re
from typing import Any, Dict

import PySide2
from PySide2 import QtWidgets, QtGui
from PySide2.QtCore import Qt

import pcot
from pcot.imagecube import ChannelMapping, ImageCube
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from .inputmethod import InputMethod
from .. import ui
from ..cameras import getCameraNames
from ..dataformats import load
from ..dataformats.raw import RawLoader
from ..parameters.taggedaggregates import TaggedDict
from ..ui import uiloader
from ..ui.presetmgr import PresetModel, PresetDialog, PresetOwner
from ..utils import SignalBlocker

logger = logging.getLogger(__name__)

# this persistently stores the presets for the multifile input method
presetModel = PresetModel(None, "MFpresets")


class MultifileInputMethod(InputMethod):
    """
    This turns a set of files into a single image. It pulls data out of the filename which it uses to lookup
    into a set of filter objects.

    For details of how this works, see the documentation for the
    pcot.dataformats.load.multifile function.

    """

    def __init__(self, inp):
        super().__init__(inp)
        # directory we're looking at
        self.dir = pcot.config.getDefaultDir('images')
        if not os.path.isdir(self.dir):
            self.dir = os.path.expanduser("~")
        # files we have checked in the file list
        self.files = []
        # bit depth - how many bits are used in the data. For example, if the data is 16 bit and only 10 bits
        # are used, set this to 10. The data will then by divided by 1023 (2^10-1) rather than 65535 (2^16-1).
        # If it is None, the data is always divided by 65535 for 16 bit data, 255 for 8 bit.
        self.bitdepth = None
        self.camera = pcot.config.default_camera
        self.filterpat = r'.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*'
        self.filterre = None
        self.rawLoader = RawLoader(offset=0, bigendian=False)

        # this is a cache used by the loader to avoid reloading files. It's a dictionary of filename
        # to data and file date.
        self.cachedFiles = {}

        self.mapping = ChannelMapping()

    def compileRegex(self):
        # compile the regexp that gets the filter ID out.
        logger.debug(f"Compiling RE: {self.filterpat}")
        try:
            self.filterre = re.compile(self.filterpat)
        except re.error:
            self.filterre = None
            logger.error("Cannot compile RE!!!!")

    def readData(self):
        # we force the mapping to have to be "reguessed"
        self.mapping.red = -1

        img = load.multifile(self.dir, self.files,
                             filterpat=self.filterpat,
                             bitdepth=self.bitdepth,
                             inpidx=self.input.idx,
                             mapping=self.mapping,
                             cache=self.cachedFiles,
                             rawloader=self.rawLoader,
                             camera=self.camera)
        logger.debug(f"------------ Image loaded: {img} from {len(self.files)} files, mapping is {self.mapping}")
        return img

    def getName(self):
        return "Multifile"

    # used from external code. Filterpat == none means leave unchanged.
    def setFileNames(self, directory, fnames, filterpat=None, camera=None) -> InputMethod:
        """This is used in scripts to set the input method to a read a set of files. It also
        takes a camera name (e.g. PANCAM) and a filter pattern. The filter pattern is a regular
        expression that is used to extract the filter name from the filename. See the class documentation
        for more information."""

        self.dir = directory
        self.files = fnames
        self.camera = camera
        if filterpat is not None:
            self.filterpat = filterpat
        self.mapping = ChannelMapping()
        return self

    def createWidget(self):
        return MultifileMethodWidget(self)

    def serialise(self, internal):
        x = {
            'dir': self.dir,
            'files': self.files,
            'bitdepth': self.bitdepth,
            'filterpat': self.filterpat,
            'camera': self.camera,
            'rawloader': self.rawLoader.serialise(),
        }
        if internal:
            x['cache'] = self.cachedFiles

        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.dir = data['dir']
        self.files = data['files']
        self.bitdepth = data.get('bitdepth', None)
        self.filterpat = data['filterpat']
        if 'rawloader' in data:
            self.rawLoader.deserialise(data['rawloader'])

        # due to names changing a lot, the camera is called "camera" in old and new data,
        # and "camera" in the middle period!
        if 'filterset' in data:
            self.camera = data['filterset']
        else:
            self.camera = data['camera']
        if internal:
            self.cachedFiles = data['cache']

        Canvas.deserialise(self, data)

    def modifyWithParameterDict(self, d: TaggedDict) -> bool:
        m = d.multifile
        if m.directory is None:
            return False  # no change to this input (directory must be provided)

        # attempt to load presets
        if m.preset is not None:
            class Preset(PresetOwner):
                """This owns presets for when we modify with a parameter dict. It sort
                of works the same way as the RawPresets in dataformats.load."""

                def __init__(self):
                    self.camera = None
                    self.filterpat = None
                    self.bitdepth = None
                    self.rawloader = None

                def applyPreset(self, preset: Dict[str, Any]):
                    self.camera = preset['camera'] if 'camera' in preset else preset['filterset']  # legacy issue
                    self.rawloader = RawLoader()
                    self.rawloader.deserialise(preset['rawloader'])
                    self.filterpat = preset['filterpat']
                    self.bitdepth = preset.get('bitdepth', None)

            preset = Preset()
            # will throw if we can't find the preset. Otherwise it will apply the loaded
            # preset to the object we just created.
            preset.applyPreset(presetModel.presets[m.preset])
            # now initialise things with the data we just loaded. Some of these may get
            # overriden further down.
            self.camera = preset.camera
            self.filterpat = preset.filterpat
            self.bitdepth = preset.bitdepth
            self.rawLoader = preset.rawloader

        # get the files
        self._getFilesFromParameterDict(m)

        # other parameters, which may override the preset IF they have been changed from their default values
        if m.isNotDefault('filter_pattern'):
            self.filterpat = m.filter_pattern
            self.compileRegex()
        if m.isNotDefault('camera'):
            self.camera = m.camera
        if m.isNotDefault('bit_depth'):
            self.bitdepth = m.bit_depth
        # and the raw parameters block. Ugly, but comprehensible.
        if m.raw is not None:
            p = m.raw
            if p.isNotDefault('format'):
                self.rawLoader.format = RawLoader.formatByName(p.format)
            if p.isNotDefault('width'):
                self.rawLoader.width = p.width
            if p.isNotDefault('height'):
                self.rawLoader.height = p.height
            if p.isNotDefault('bigendian'):
                self.rawLoader.bigendian = p.bigendian
            if p.isNotDefault('offset'):
                self.rawLoader.offset = p.offset
            if p.isNotDefault('rot'):
                self.rawLoader.rot = p.rot
            if p.isNotDefault('horzflip'):
                self.rawLoader.horzflip = p.horzflip
            if p.isNotDefault('vertflip'):
                self.rawLoader.vertflip = p.vertflip
        return True


# Then the UI class...

IMAGETYPERE = re.compile(r".*\.(?i:jpg|bmp|png|ppm|tga|tif|raw|bin)")


class MultifileMethodWidget(MethodWidget, PresetOwner):
    def __init__(self, m):
        super().__init__(m)
        uiloader.loadUi('inputmultifile.ui', self)
        self.model = None
        # all the files in the current directory (which match the filters)
        self.allFiles = []
        # these record the image last clicked on - we need to do that so we can
        # regenerate it with new sources if the camera is changed
        self.activatedImagePath = None
        self.activatedImage = None
        self.getinitial.clicked.connect(self.getInitial)
        self.filelist.activated.connect(self.itemActivated)
        self.filterpat.editingFinished.connect(self.patChanged)
        self.bitdepth.currentTextChanged.connect(self.bitdepthChanged)
        self.cameraCombo.currentIndexChanged.connect(self.cameraChanged)
        self.loaderSettingsButton.clicked.connect(self.loaderSettings)
        self.loaderSettingsText.setText(str(self.method.rawLoader))
        self.presetButton.pressed.connect(self.presetPressed)
        # self.canvas.hideMapping()  # because we're showing greyscale for each image
        self.canvas.setGraph(self.method.input.mgr.doc.graph)
        self.canvas.setPersister(m)

        self.filelist.setMinimumWidth(300)
        self.setMinimumSize(1000, 500)
        pcot.ui.decorateSplitter(self.splitter, 1)

        with SignalBlocker(self.cameraCombo):
            self.cameraCombo.addItems(getCameraNames())

        # if the method doesn't have a directory, reset to the default.

        if self.method.dir is None or len(self.method.dir) == 0:
            self.method.dir = pcot.config.getDefaultDir('images')
        self.onInputChanged()

    def applyPreset(self, preset):
        # see comments in presetPressed for why this is here and not in the input method
        self.method.camera = preset['camera']
        self.method.rawLoader.deserialise(preset['rawloader'])
        self.method.filterpat = preset['filterpat']
        self.method.bitdepth = preset.get('bitdepth', None)
        self.onInputChanged()

    def fetchPreset(self):
        # see comments in presetPressed for why this is here and not in the input method
        return {
            "camera": self.method.camera,
            "rawloader": self.method.rawLoader.serialise(),
            "filterpat": self.method.filterpat,
            "bitdepth": self.method.bitdepth
        }

    def cameraChanged(self, i):
        self.method.camera = self.cameraCombo.currentText()
        self.onInputChanged()

    def presetPressed(self):
        # here, the "owner" of the preset dialog is actually this dialog - not the input itself - because
        # we need to update the dialog when the preset is applied.
        w = PresetDialog(self, "Multifile presets", presetModel, self)
        w.exec_()
        self.onInputChanged()

    def loaderSettings(self):
        self.method.rawLoader.edit(self)
        # clear the cache, we'll need to reload those files!
        self.method.cachedFiles = {}
        self.loaderSettingsText.setText(str(self.method.rawLoader))

    def onInputChanged(self):
        # the method has changed - set the filters text widget and reselect the dir.
        # This will only clear the selected files if we changed the dir.
        self.loaderSettingsText.setText(str(self.method.rawLoader))
        self.selectDir(self.method.dir)
        s = ""
        for i in range(len(self.method.files)):
            s += "{}:\t{}\n".format(i, self.method.files[i])
        #        s+="\n".join([str(x) for x in self.node.imgpaths])
        self.outputFiles.setPlainText(s)
        if self.method.bitdepth is not None:
            i = self.bitdepth.findText(str(int(self.method.bitdepth)) + ' ', Qt.MatchFlag.MatchStartsWith)
        else:
            i = 0
        self.bitdepth.setCurrentIndex(i)
        self.filterpat.setText(self.method.filterpat)
        # this won't work if the camera isn't in the combobox.
        self.cameraCombo.setCurrentText(self.method.camera)
        self.displayActivatedImage()
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
            self.method.input.performGraph()
        self.method.compileRegex()
        self.canvas.display(self.method.get())

    def fileClickedAction(self, idx):
        if not self.dirModel.isDir(idx):
            self.method.img = None
            self.method.fname = os.path.realpath(self.dirModel.filePath(idx))
            self.method.get()
            self.onInputChanged()

    def getInitial(self):
        # select a directory
        d = pcot.config.getDefaultDir('images')
        res = QtWidgets.QFileDialog.getExistingDirectory(None, 'Directory for images',
                                                         os.path.expanduser(d),
                                                         options=pcot.config.getFileDialogOptions())
        if res != '':
            self.selectDir(res, True)

    def selectDir(self, dr, setDefaultDir=False):
        # called when we want to load a new directory, or when the node has changed (on loading)
        if self.method.dir != dr:  # if the directory has changed reset the selected file list
            self.method.files = []
            ## TODO self.method.type.clearImages(self.node)
        self.dir.setText(dr)
        # get all the files in dir which are images
        try:
            self.allFiles = sorted([f for f in os.listdir(dr) if os.path.isfile(os.path.join(dr, f))
                                    and IMAGETYPERE.match(f) is not None])
            # using the absolute, real path
            self.method.dir = os.path.realpath(dr)
            # only set the default directory for images when this is called "manually" - typically in response
            # to the "get directory" button.
            if setDefaultDir:
                pcot.config.setDefaultDir('images', self.method.dir)
        except Exception as e:
            # some kind of file system error
            e = str(e)
            self.method.input.exception = str(e)
            ui.error(e)

        # rebuild the model
        self.buildModel()

    def patChanged(self):
        self.method.filterpat = self.filterpat.text()
        self.onInputChanged()

    def bitdepthChanged(self, s):
        try:
            # strings in the combobox are typically "10 bits" or "FulL"
            if s == "Full":
                self.method.bitdepth = None
            else:
                ll = s.split()
                if len(ll) > 0:
                    self.method.bitdepth = int(ll[0])
                    self.onInputChanged()
        except (ValueError, OverflowError):
            raise Exception("CTRL", "Bad bitdepth string in 'multifile': " + s)

    def buildModel(self):
        # build the model that the list view uses
        self.model = QtGui.QStandardItemModel(self.filelist)
        for x in self.allFiles:
            # create a checkable item for each file, and check the checkbox
            # if it is in the files list
            item = QtGui.QStandardItem(x)
            item.setCheckable(True)
            if x in self.method.files:
                item.setCheckState(PySide2.QtCore.Qt.Checked)
            self.model.appendRow(item)

        self.filelist.setModel(self.model)
        self.model.dataChanged.connect(self.checkedChanged)

    def itemActivated(self, idx):
        # called when we "activate" an item, typically by doubleclicking: load the file
        # to preview it
        item = self.model.itemFromIndex(idx)
        path = os.path.join(self.method.dir, item.text())
        self.method.compileRegex()
        if RawLoader.is_raw_file(path):
            # if it's a raw file, load it with the raw loader and create an ImageCube
            arr = self.method.rawLoader.load(path, bitdepth=self.method.bitdepth)
            img = ImageCube(arr, self.method.mapping)
        else:
            # otherwise load it with the ImageCube RGB loader
            img = ImageCube.load(path, self.method.mapping, None,
                                 bitdepth=self.method.bitdepth)  # RGB image, null sources

        self.activatedImagePath = path
        self.activatedImage = img
        self.displayActivatedImage()

    def displayActivatedImage(self):
        if self.activatedImage:
            # we're creating a temporary greyscale image here. We could use an Source
            # as usual, but that won't work because it assumes the input is already set up.
            # There's really not much point in using a source at all, though, so we'll just
            # use null sources here - and those will already be loaded by .load().
            self.canvas.display(self.activatedImage)

    def checkedChanged(self):
        # the checked items have changed, reset the list and regenerate
        # the files list
        self.method.files = []
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.checkState() == Qt.Checked:
                self.method.files.append(item.text())
        self.onInputChanged()
