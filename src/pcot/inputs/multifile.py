## the Multifile input method, inputting several greyscale images
# into a single image
import logging
import os
import re

import PySide2
import numpy as np
from PySide2 import QtWidgets, QtGui
from PySide2.QtCore import Qt

import pcot
from pcot.imagecube import ChannelMapping, ImageCube
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from .inputmethod import InputMethod
from .. import ui
from ..dataformats import load
from ..dataformats.raw import RawLoader
from ..filters import getFilterSetNames
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
        # all data in all channels is multiplied by this (used for, say, 10 bit images)
        self.mult = 1
        self.filterset = "PANCAM"
        self.filterpat = r'.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*'
        self.filterre = None
        self.rawLoader = RawLoader(offset=0, bigendian=False)

        # this is a cache used by the loader to avoid reloading files. It's a dictionary of filename
        # to data and file date.
        self.cachedFiles = {}

        self.mapping = ChannelMapping()

    def compileRegex(self):
        # compile the regexp that gets the filter ID out.
        logger.info(f"Compiling RE: {self.filterpat}")
        try:
            self.filterre = re.compile(self.filterpat)
        except re.error:
            self.filterre = None
            logger.error("Cannot compile RE!!!!")

    def readData(self):
        # we force the mapping to have to be "reguessed"
        self.mapping.red = -1

        return load.multifile(self.dir, self.files,
                              filterpat=self.filterpat,
                              mult=np.float32(self.mult),
                              inpidx=self.input.idx,
                              mapping=self.mapping,
                              cache=self.cachedFiles,
                              rawloader=self.rawLoader,
                              filterset=self.filterset)

    def getName(self):
        return "Multifile"

    # used from external code. Filterpat == none means leave unchanged.
    def setFileNames(self, directory, fnames, filterpat=None, filterset="PANCAM") -> InputMethod:
        """This is used in scripts to set the input method to a read a set of files. It also
        takes a filter set name (e.g. PANCAM) and a filter pattern. The filter pattern is a regular
        expression that is used to extract the filter name from the filename. See the class documentation
        for more information."""

        self.dir = directory
        self.files = fnames
        self.filterset = filterset
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
             'mult': self.mult,
             'filterpat': self.filterpat,
             'filterset': self.filterset,
             'rawloader': self.rawLoader.serialise(),
             }
        if internal:
            x['cache'] = self.cachedFiles

        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.dir = data['dir']
        self.files = data['files']
        self.mult = data['mult']
        self.filterpat = data['filterpat']
        if 'rawloader' in data:
            self.rawLoader.deserialise(data['rawloader'])

        # deal with legacy files where "filterset" is called "camera"
        if 'filterset' in data:
            self.filterset = data['filterset']
        else:
            self.filterset = data['camera']
        if internal:
            self.cachedFiles = data['cache']

        Canvas.deserialise(self, data)


# Then the UI class..


IMAGETYPERE = re.compile(r".*\.(?i:jpg|bmp|png|ppm|tga|tif|raw|bin)")


class MultifileMethodWidget(MethodWidget, PresetOwner):
    def __init__(self, m):
        super().__init__(m)
        uiloader.loadUi('inputmultifile.ui', self)
        self.model = None
        # all the files in the current directory (which match the filters)
        self.allFiles = []
        # these record the image last clicked on - we need to do that so we can
        # regenerate it with new sources if the filter set is changed
        self.activatedImagePath = None
        self.activatedImage = None
        self.getinitial.clicked.connect(self.getInitial)
        self.filelist.activated.connect(self.itemActivated)
        self.filterpat.editingFinished.connect(self.patChanged)
        self.mult.currentTextChanged.connect(self.multChanged)
        self.filtSetCombo.currentIndexChanged.connect(self.filterSetChanged)
        self.loaderSettingsButton.clicked.connect(self.loaderSettings)
        self.loaderSettingsText.setText(str(self.method.rawLoader))
        self.canvas.setMapping(m.mapping)
        self.presetButton.pressed.connect(self.presetPressed)
        # self.canvas.hideMapping()  # because we're showing greyscale for each image
        self.canvas.setGraph(self.method.input.mgr.doc.graph)
        self.canvas.setPersister(m)

        self.filelist.setMinimumWidth(300)
        self.setMinimumSize(1000, 500)

        with SignalBlocker(self.filtSetCombo):
            self.filtSetCombo.addItems(getFilterSetNames())

        if self.method.dir is None or len(self.method.dir) == 0:
            self.method.dir = pcot.config.getDefaultDir('images')
        self.onInputChanged()

    def applyPreset(self, preset):
        # see comments in presetPressed for why this is here and not in the input method
        self.method.filterset = preset['filterset']
        self.method.rawLoader.deserialise(preset['rawloader'])
        self.method.filterpat = preset['filterpat']
        self.method.mult = preset['mult']
        self.onInputChanged()

    def fetchPreset(self):
        # see comments in presetPressed for why this is here and not in the input method
        return {
            "filterset": self.method.filterset,
            "rawloader": self.method.rawLoader.serialise(),
            "filterpat": self.method.filterpat,
            "mult": self.method.mult
        }

    def filterSetChanged(self, i):
        self.method.filterset = self.filtSetCombo.currentText()
        self.onInputChanged()

    def presetPressed(self):
        # here, the "owner" of the preset dialog is actually this dialog - not the input itself - because
        # we need to update the dialog when the preset is applied.
        w = PresetDialog(self, "Multifile presets", presetModel, self)
        w.exec_()
        self.onInputChanged()

    def loaderSettings(self):
        self.method.rawLoader.edit(self)
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
        i = self.mult.findText(str(int(self.method.mult)) + ' ', Qt.MatchFlag.MatchStartsWith)
        self.mult.setCurrentIndex(i)
        self.filterpat.setText(self.method.filterpat)
        # this won't work if the filter set isn't in the combobox.
        self.filtSetCombo.setCurrentText(self.method.filterset)
        self.displayActivatedImage()
        self.invalidate()  # input has changed, invalidate so the cache is dirtied
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
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
            self.selectDir(res)

    def selectDir(self, dr):
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

    def multChanged(self, s):
        try:
            # strings in the combobox are typically "64 (6 bit shift)"
            ll = s.split()
            if len(ll) > 0:
                self.method.mult = float(ll[0])
                self.onInputChanged()
        except (ValueError, OverflowError):
            raise Exception("CTRL", "Bad mult string in 'multifile': " + s)

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
            arr = self.method.rawLoader.load(path)
            img = ImageCube(arr, self.method.mapping)
        else:
            # otherwise load it with the ImageCube RGB loader
            img = ImageCube.load(path, self.method.mapping, None)  # RGB image, null sources
        img.img *= self.method.mult
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
