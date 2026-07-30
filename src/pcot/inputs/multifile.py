## the Multifile input method, inputting several greyscale images
# into a single image
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

import PySide6
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt

import pcot
from pcot.imagecube import ChannelMapping, ImageCube
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from pcot.inputs.inputmethod import InputMethod
from pcot import ui
from pcot.cameras import getCameraNames
from pcot.dataformats import load
from pcot.dataformats.raw import RawLoader
from pcot.parameters.taggedaggregates import TaggedDict
from pcot.ui import uiloader
from pcot.ui.presetmgr import PresetModel, PresetDialog, PresetOwner
from pcot.utils import SignalBlocker

logger = logging.getLogger(__name__)

# this persistently stores the presets for the multifile input method
presetModel = PresetModel(None, "MFpresets")


class MultifileInputMethod(InputMethod, PresetOwner):
    """
    This turns a set of files into a single image. It pulls data out of the filename which it uses to lookup
    into a set of filter objects.

    For details of how this works, see the documentation for the
    pcot.dataformats.load.multifile function.

    """

    def __init__(self, inp):
        super().__init__(inp)
        # directory we're looking at
        tmp = pcot.config.getDefaultDir('images')
        self.dir = Path(tmp) if tmp is not None else None

        if not self.dir or not self.dir.is_dir():
            self.dir = Path.home()

        # files we have checked in the file list
        self.files = []
        # bit depth - how many bits are used in the data. For example, if the data is 16 bit and only 10 bits
        # are used, set this to 10. The data will then by divided by 1023 (2^10-1) rather than 65535 (2^16-1).
        # If it is None, the data is always divided by 65535 for 16 bit data, 255 for 8 bit.
        self.bitdepth = None
        # if True, the significant bits given by bitdepth are assumed to occupy the top of their container
        # (e.g. a 10-bit value stored in the top of a 16-bit word, with the bottom 6 bits always zero) rather
        # than the bottom. Has no effect if bitdepth is None. Defaults on for new inputs, but old documents
        # which predate this setting are loaded as if it were off, to preserve their existing appearance.
        self.leftjustified = True
        self.camera = pcot.config.data.default_camera
        self.filterpat = pcot.config.data.multifile_pattern
        self.filterre = None
        self.rawLoader = RawLoader(offset=0, bigendian=False)

        # this is a cache used by the loader to avoid reloading files. It's a dictionary of filename
        # to data and file date.
        self.cachedFiles = {}

        self.mapping = ChannelMapping()

        # per-file DN range from the most recent successful load, keyed by filename
        # (matches entries in self.files). Transient, not serialised - repopulated by readData().
        self.dnRanges: Dict[str, Tuple[float, float]] = {}
        # whether readData() has actually run this session - False for a document just loaded from
        # a .pcot file, where the image data is cached and the files haven't really been re-read. Used
        # to distinguish "(cached)" from "(failed)" in the file listing for files with no dnRanges entry.
        self.dnRangesAttempted = False

    def compileRegex(self):
        # compile the regexp that gets the filter ID out.
        logger.debug(f"Compiling RE: {self.filterpat}")
        try:
            self.filterre = re.compile(self.filterpat)
        except re.error:
            self.filterre = None
            logger.error("Cannot compile RE!!!!")

    def setRawLoader(self, loader):
        if loader:
            self.rawLoader = loader

    def invalidate(self, force=False):
        """Invalidates the internal cache for this method as well as clearing the output.
        See InputMethod.invalidate() - a no-op if the source directory is confirmed missing,
        unless force is set (the per-file caches are only cleared in that case too, so a
        missing directory doesn't lose its last successfully assembled image)."""
        if not force and self.missingPathReason() is not None:
            logger.debug("Multifile invalidate skipped - source missing, keeping cached data")
            return
        self.cachedFiles = {}
        self.dnRanges = {}
        super().invalidate(force=force)

    def missingPathReason(self) -> Optional[str]:
        if self.dir is None:
            return None
        if not os.path.isdir(str(self.dir)):
            return f"Directory not found: {self.dir}{self._cachedDataSuffix()}"
        # the directory itself is fine, but one or more of the individually-selected files
        # within it might have been deleted since - check those too (still a cheap check:
        # a handful of stat calls, one per selected file).
        missing = [f for f in self.files if not os.path.isfile(os.path.join(str(self.dir), f))]
        if missing:
            if len(missing) == 1:
                return f"File not found: {os.path.join(str(self.dir), missing[0])}{self._cachedDataSuffix()}"
            return f"{len(missing)} input files not found in directory: {self.dir}{self._cachedDataSuffix()}"
        return None

    def readData(self):
        # we force the mapping to have to be "reguessed"
        self.mapping.red = -1
        self.dnRanges = {}
        self.dnRangesAttempted = True

        img = load.multifile(self.dir, self.files,
                             filterpat=self.filterpat,
                             bitdepth=self.bitdepth,
                             leftjustified=self.leftjustified,
                             inpidx=self.input.idx,
                             mapping=self.mapping,
                             cache={},     # TODO put the cache back!!!! Not being invalidated making debug hard
                             rawloader=self.rawLoader,
                             camera=self.camera,
                             dn_ranges=self.dnRanges)
        logger.debug(f"------------ Image loaded: {img} from {len(self.files)} files, mapping is {self.mapping}")
        return img

    def getName(self):
        return "Multifile"

    # used from external code. Filterpat == none means leave unchanged.
    def setFileNames(self, directory, fnames, filterpat=None, camera=None, bitdepth=None,
                     leftjustified=False) -> InputMethod:
        """This is used in scripts to set the input method to a read a set of files. It also
        takes a camera name (e.g. PANCAM) and a filter pattern. The filter pattern is a regular
        expression that is used to extract the filter name from the filename. See the class documentation
        for more information. We also accept bitdepth - None means the full depth is used - and
        leftjustified, which says whether the significant bits occupy the top of the container."""

        self.dir = directory
        self.files = fnames
        self.camera = camera
        self.bitdepth = bitdepth
        self.leftjustified = leftjustified
        if filterpat is not None:
            self.filterpat = filterpat
        self.mapping = ChannelMapping()
        return self

    def createWidget(self):
        return MultifileMethodWidget(self)

    def serialise(self, internal):
        x = {
            'dir': str(self.dir),
            'files': self.files,
            'bitdepth': self.bitdepth,
            'leftjustified': self.leftjustified,
            'filterpat': self.filterpat,
            'camera': self.camera,
            'rawloader': self.rawLoader.serialise(),
        }
        if internal:
            x['cache'] = self.cachedFiles

        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.dir = Path(data['dir'])
        self.files = data['files']
        self.bitdepth = data.get('bitdepth', None)
        # old documents which predate this setting are loaded as if it were off, to preserve
        # their existing appearance rather than silently changing already-saved images.
        self.leftjustified = data.get('leftjustified', False)
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

    def fetchPreset(self) -> Dict[str, Any]:
        """Fetch the current loader settings as a preset dict. This is the canonical
        multifile preset field set (camera, filterpat, bitdepth, leftjustified, rawloader),
        used - directly or via a thin delegator - by the GUI widget, the parameter-file/
        batch loader, and the scripting load.multifile() path."""
        return {
            "camera": self.camera,
            "rawloader": self.rawLoader.serialise(),
            "filterpat": self.filterpat,
            "bitdepth": self.bitdepth,
            "leftjustified": self.leftjustified,
        }

    def applyPreset(self, preset: Dict[str, Any]):
        """Apply a preset dict (as produced by fetchPreset(), or a hand-built/legacy one)
        to this method's fields. This is the single canonical implementation of preset
        application for multifile - all other preset-owner code paths call this rather
        than re-implementing the field list.

        Compatibility notes:
        - 'camera' was previously called 'filterset'; very old presets may still use that
          key, so we fall back to it if 'camera' isn't present.
        - 'bitdepth' and 'leftjustified' are optional (older presets predate them).
          leftjustified defaults to False when missing - NOT the True default used for
          brand new inputs - so old presets don't silently change behaviour, matching the
          choice already made in deserialise() for whole documents.
        - 'rawloader' is always required; if it's missing this raises KeyError, matching
          the behaviour every existing preset-owner implementation already had.
        """
        self.camera = preset['camera'] if 'camera' in preset else preset['filterset']
        self.filterpat = preset['filterpat']
        self.bitdepth = preset.get('bitdepth', None)
        self.leftjustified = preset.get('leftjustified', False)
        self.rawLoader.deserialise(preset['rawloader'])

    def modifyWithParameterDict(self, d: TaggedDict) -> bool:
        m = d.multifile
        if m.directory is None:
            return False  # no change to this input (directory must be provided)

        # attempt to load presets - applied directly as defaults; explicit parameter-file
        # fields checked via isNotDefault() below may override them.
        if m.preset is not None:
            self.applyPreset(presetModel.loadPresetByName(m.preset))

        # get the files
        self._getFilesFromParameterDict(m)

        # other parameters, which may override the preset IF they have been changed from their default values
        if m.isNotDefault('filter_pattern'):    # the default here is None, so we won't ever write None to the filterpat.
            self.filterpat = m.filter_pattern
            self.compileRegex()
        if m.isNotDefault('camera'):
            self.camera = m.camera
        if m.isNotDefault('bit_depth'):
            self.bitdepth = m.bit_depth
        if m.isNotDefault('left_justified'):
            self.leftjustified = m.left_justified
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
        # populate bit depth widget
        self.bitdepth.addItem("Full")
        for x in range(10,16):
            self.bitdepth.addItem(f"{x} bits")

        # these record the image last clicked on - we need to do that so we can
        # regenerate it with new sources if the camera is changed
        self.activatedImagePath = None
        self.activatedImage = None
        self.getinitial.clicked.connect(self.getInitial)
        self.filelist.activated.connect(self.itemActivated)
        self.filterpat.editingFinished.connect(self.patChanged)
        self.bitdepth.currentTextChanged.connect(self.bitdepthChanged)
        self.leftJustified.toggled.connect(self.leftJustifiedChanged)
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

        self.outputFiles.horizontalHeader().setSectionsMovable(True)
        self.outputFiles.horizontalHeader().setStretchLastSection(True)

        with SignalBlocker(self.cameraCombo):
            self.cameraCombo.addItems(getCameraNames())

        # if the method doesn't have a directory, reset to the default.

        if self.method.dir is None:
            self.method.dir = pcot.config.getDefaultDir('images')
        self.syncIfActive()

    def onClose(self):
        super().onClose()
        self.canvas.onClose()

    def applyPreset(self, preset):
        # see comments in presetPressed for why this is here and not in the input method:
        # applying a preset changes self.method's fields, but only the widget knows which
        # bits of UI (combo boxes, checkboxes, canvas, graph re-run) need refreshing
        # afterwards.
        self.method.applyPreset(preset)
        self.onInputChanged()

    def fetchPreset(self):
        # see comments in presetPressed for why this is here and not in the input method
        return self.method.fetchPreset()

    def cameraChanged(self, i):
        self.method.camera = self.cameraCombo.currentText()
        self.onInputChanged()

    def presetPressed(self):
        # here, the "owner" of the preset dialog is actually this dialog - not the input itself - because
        # we need to update the dialog when the preset is applied.
        w = PresetDialog(self, "Multifile presets", presetModel, self)
        w.exec()
        self.onInputChanged()

    def loaderSettings(self):
        self.method.rawLoader.edit(self)
        # clear the cache, we'll need to reload those files!
        self.method.invalidate()
        self.loaderSettingsText.setText(str(self.method.rawLoader))

    def onInputChanged(self):
        # the method has changed - set the filters text widget and refresh the file list
        # from the method's directory (without ever changing that directory - see
        # refreshFileList()).
        self.loaderSettingsText.setText(str(self.method.rawLoader))
        self.refreshFileList()
        if self.method.bitdepth is not None:
            i = self.bitdepth.findText(str(int(self.method.bitdepth)) + ' ', Qt.MatchFlag.MatchStartsWith)
        else:
            i = 0
        self.bitdepth.setCurrentIndex(i)
        self.leftJustified.setChecked(self.method.leftjustified)
        self.filterpat.setText(self.method.filterpat)
        # this won't work if the camera isn't in the combobox.
        self.cameraCombo.setCurrentText(self.method.camera)
        self.displayActivatedImage()
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.invalidate()  # input has changed, invalidate so the cache is dirtied
            self.method.input.performGraph()
        self.method.compileRegex()

        datum = self.method.get()  # (re)loads if needed - populates self.method.dnRanges
        self.canvas.display(datum)

        # build the per-file listing after the load, so DN ranges (if any) are current
        self.outputFiles.setRowCount(len(self.method.files))
        for i, fname in enumerate(self.method.files):
            rng = self.method.dnRanges.get(fname)
            if rng is not None:
                rngText = "[{:g}, {:g}]".format(*rng)
            elif not self.method.dnRangesAttempted:
                rngText = "(cached)"
            else:
                rngText = "(failed)"
            self.outputFiles.setItem(i, 0, QtWidgets.QTableWidgetItem(fname))
            self.outputFiles.setItem(i, 1, QtWidgets.QTableWidgetItem(rngText))
        self.outputFiles.resizeColumnToContents(0)

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

    @staticmethod
    def _listImageFiles(dr):
        """List image files in a directory; propagates any exception (e.g. dir doesn't exist)."""
        return sorted([f for f in os.listdir(dr) if os.path.isfile(os.path.join(dr, f))
                       and IMAGETYPERE.match(f) is not None])

    def refreshFileList(self):
        """Populate the file list from self.method.dir, without ever mutating that directory.
        If it can't be read (most commonly because the document was created on a different
        machine and the original directory isn't present here), just show an empty list -
        the method's tab button carries a marker/tooltip explaining why, rather than us
        guessing at some unrelated fallback directory to browse instead."""
        dr = self.method.dir
        self.dir.setText(str(dr) if dr is not None else "")
        try:
            self.allFiles = self._listImageFiles(dr) if dr is not None else []
        except Exception as e:
            logger.info(f"Multifile: configured directory not available ({dr}): {e}")
            self.allFiles = []
        self.buildModel()
        self.refreshMissingIndicator()

    def selectDir(self, dr, setDefaultDir=False):
        """Called when the user explicitly picks a new directory (via the 'get directory'
        button) - dr becomes the new, real value of self.method.dir."""
        if self.method.dir != dr:  # if the directory has changed reset the selected file list
            self.method.files = []
            ## TODO self.method.type.clearImages(self.node)
        try:
            allFiles = self._listImageFiles(dr)
        except Exception as e:
            # a directory picked via the file dialog should always exist, but be defensive
            ui.error(str(e))
            return
        self.allFiles = allFiles
        self.method.dir = Path(os.path.realpath(dr))
        self.dir.setText(str(self.method.dir))
        # only set the default directory for images when this is called "manually" - typically in response
        # to the "get directory" button.
        if setDefaultDir:
            pcot.config.setDefaultDir('images', self.method.dir)
        self.buildModel()
        self.refreshMissingIndicator()

    def patChanged(self):
        self.method.filterpat = self.filterpat.text()
        self.onInputChanged()

    def leftJustifiedChanged(self, checked):
        self.method.leftjustified = checked
        self.onInputChanged()

    def bitdepthChanged(self, s):
        try:
            # strings in the combobox are typically "10 bits" or "FulL"
            if s == "Full":
                self.method.bitdepth = None
                self.onInputChanged()
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

        # any previously-selected files that aren't in the current listing (individually
        # deleted, or the whole directory couldn't be read) are shown first, in red, so
        # they're immediately visible rather than buried at the bottom of a long list -
        # the selection doesn't just silently vanish, the user can see exactly what's missing.
        redBrush = QtGui.QBrush(QtGui.QColor(200, 0, 0))
        for x in self.method.files:
            if x not in self.allFiles:
                item = QtGui.QStandardItem(x)
                item.setCheckable(True)
                item.setCheckState(PySide6.QtCore.Qt.CheckState.Checked)
                item.setForeground(redBrush)
                item.setToolTip("This file could not be found")
                self.model.appendRow(item)

        for x in self.allFiles:
            # create a checkable item for each file, and check the checkbox
            # if it is in the files list
            item = QtGui.QStandardItem(x)
            item.setCheckable(True)
            if x in self.method.files:
                item.setCheckState(PySide6.QtCore.Qt.CheckState.Checked)
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
            arr, dn_min, dn_max = self.method.rawLoader.load(path, bitdepth=self.method.bitdepth,
                                             leftjustified=self.method.leftjustified)
            img = ImageCube(arr, self.method.mapping)
            img.dnRange = (dn_min, dn_max)
        else:
            # otherwise load it with the ImageCube RGB loader
            img = ImageCube.load(path, self.method.mapping, None,
                                 bitdepth=self.method.bitdepth,
                                 leftjustified=self.method.leftjustified)  # RGB image, null sources

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
            if item.checkState() == Qt.CheckState.Checked:
                self.method.files.append(item.text())
        self.onInputChanged()
