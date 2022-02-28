## the Multifile input method, inputting several greyscale images
# into a single image
import logging
import os
import re

import PyQt5
import cv2 as cv
from PyQt5 import uic, QtWidgets, QtGui
from PyQt5.QtCore import Qt

import pcot
from .inputmethod import InputMethod
from pcot.imagecube import ChannelMapping, ImageCube
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from .. import ui
from ..datum import Datum
from ..filters import getFilterByPos
from ..sources import InputSource, SourceSet, MultiBandSource


logger = logging.getLogger(__name__)


class MultifileInputMethod(InputMethod):
    def __init__(self, inp):
        super().__init__(inp)
        # list of filter strings - strings which must be in any filenames
        self.namefilters = []
        # directory we're looking at
        self.dir = pcot.config.getDefaultDir('images')
        if not os.path.isdir(self.dir):
            self.dir = os.path.expanduser("~")
        # files we have checked in the file list
        self.files = []
        # all data in all channels is multiplied by this (used for, say, 10 bit images)
        self.mult = 1
        self.camera = "PANCAM"
        self.filterpat = r'.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*'
        self.filterre = None
        # dict of files we currently have, fullpath -> imagecube
        self.cachedFiles = {}

        self.mapping = ChannelMapping()
        self.img = None

    def long(self):
        lst = [f"{i}: {f}" for i, f in enumerate(self.files)]
        return f"MULTI: path={self.dir} {', '.join(lst)}]"

    def getFilterName(self, path):
        if self.filterre is None:
            return None
        else:
            m = self.filterre.match(path)
            if m is None:
                return None
            m = m.groupdict()
            lens = m['lens'] if 'lens' in m else ''
            n = m['n'] if 'n' in m else ''
            return lens + n

    def compileRegex(self):
        # compile the regexp that gets the filter ID out.
        try:
            self.filterre = re.compile(self.filterpat)
        except re.error:
            self.filterre = None

    def readData(self):
        self.compileRegex()

        doc = self.input.mgr.doc
        inpidx = self.input.idx

        sources = []  # array of source sets for each image
        imgs = []  # array of actual images (greyscale, numpy)
        newCachedFiles = {}  # will replace the old cache data
        # perform takes all the images in the outputs and bundles them into a single image.
        # They all have to be the same size, and they're all converted to greyscale.
        for i in range(len(self.files)):
            if self.files[i] is not None:
                # we use the relative path here, it's more right that using the absolute path
                # most of the time.
                # CORRECTION: but it doesn't work if no relative paths exists (e.g. different drives)
                try:
                    path = os.path.relpath(os.path.join(self.dir, self.files[i]))
                except ValueError:
                    path = os.path.abspath(os.path.join(self.dir, self.files[i]))

                # build sources data : filename and filter name
                filtpos = self.getFilterName(path)   # says name, but usually is the position.
                filt = getFilterByPos(filtpos, self.camera == 'AUPE')
                source = InputSource(doc, inpidx, filt)

                # is it in the cache?
                if path in self.cachedFiles:
                    logger.debug("IMAGE IN MULTIFILE CACHE: NOT PERFORMING FILE READ")
                    img = self.cachedFiles[path]
                else:
                    logger.debug("IMAGE NOT IN MULTIFILE CACHE: PERFORMING FILE READ")
                    # use image cube loader even though we're just going to use the numpy image - just easier.
                    img = ImageCube.load(path, None, None)  # always RGB at this point
                    # aaaand this pretty much always happens, because load always
                    # loads as BGR.
                    if img.channels != 1:
                        c = cv.split(img.img)[0]  # just use channel 0
                        img = ImageCube(c, None, None)
                # store in cache
                newCachedFiles[path] = img
                imgs.append(img.img)  # store numpy image
                sources.append(source)

        # replace the old cache dict with the new one we have built
        self.cachedFiles = newCachedFiles
        # assemble the images - cv.merge can cope with non-3 channels
        if len(imgs) > 0:
            img = cv.merge(imgs)
            img = ImageCube(img * self.mult, self.mapping, MultiBandSource(sources))
        else:
            img = None
        return Datum(Datum.IMG, img)

    def getName(self):
        return "Multifile"

    # used from external code
    def setFileNames(self, directory, fnames):
        self.dir = directory
        self.files = fnames
        self.mapping = ChannelMapping()

    def createWidget(self):
        return MultifileMethodWidget(self)

    def serialise(self, internal):
        x = {'namefilters': self.namefilters,
             'dir': self.dir,
             'files': self.files,
             'mult': self.mult,
             'filterpat': self.filterpat,
             'camera': self.camera,
             }
        if internal:
            x['cache'] = self.cachedFiles
            x['img'] = self.img

        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.namefilters = data['namefilters']
        self.dir = data['dir']
        self.files = data['files']
        self.mult = data['mult']
        self.filterpat = data['filterpat']
        self.camera = data['camera']
        if internal:
            self.cachedFiles = data['cache']
            self.img = data['img']

        Canvas.deserialise(self, data)


# Then the UI class..


IMAGETYPERE = re.compile(r".*\.(?i:jpg|png|ppm|tga|tif)")


class MultifileMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        self.model = None
        uic.loadUi(pcot.config.getAssetAsFile('inputmultifile.ui'), self)
        self.getinitial.clicked.connect(self.getInitial)
        self.filters.textChanged.connect(self.filtersChanged)
        self.filelist.activated.connect(self.itemActivated)
        self.filterpat.editingFinished.connect(self.patChanged)
        self.mult.currentTextChanged.connect(self.multChanged)
        self.camCombo.currentIndexChanged.connect(self.cameraChanged)
        self.canvas.setMapping(m.mapping)
        self.canvas.hideMapping()  # because we're showing greyscale for each image
        self.canvas.setGraph(self.method.input.mgr.doc.graph)
        self.canvas.setPersister(m)

        self.filelist.setMinimumWidth(300)
        self.setMinimumSize(1000, 500)

        # these record the image last clicked on - we need to do that so we can
        # regenerate it with new sources if the camera setting is change.d
        self.activatedImagePath = None
        self.activatedImage = None
        # all the files in the current directory (which match the filters)
        self.allFiles = []
        self.method.dir = pcot.config.getDefaultDir('images')
        self.onInputChanged()

    def cameraChanged(self, i):
        self.method.camera = "PANCAM" if i == 0 else "AUPE"
        self.onInputChanged()

    def onInputChanged(self):
        # the method has changed - set the filters text widget and reselect the dir.
        # This will only clear the selected files if we changed the dir.
        self.filters.setText(",".join(self.method.namefilters))
        self.selectDir(self.method.dir)
        s = ""
        for i in range(len(self.method.files)):
            s += "{}:\t{}\n".format(i, self.method.files[i])
        #        s+="\n".join([str(x) for x in self.node.imgpaths])
        self.outputFiles.setPlainText(s)
        i = self.mult.findText(str(int(self.method.mult)))
        self.mult.setCurrentIndex(i)
        self.filterpat.setText(self.method.filterpat)
        self.camCombo.setCurrentIndex(1 if self.method.camera == 'AUPE' else 0)
        self.displayActivatedImage()
        self.invalidate()  # input has changed, invalidate so the cache is dirtied
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.method.input.performGraph()
        self.canvas.display(self.method.img)

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
                                                         os.path.expanduser(d))
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

    def filtersChanged(self, t):
        # rebuild the filter list from the comma-sep string and rebuild the model
        self.method.namefilters = t.split(",")
        self.buildModel()

    def multChanged(self, s):
        try:
            self.method.mult = float(s)
            self.onInputChanged()  # TODO was self.changed
        except (ValueError, OverflowError):
            raise Exception("CTRL", "Bad mult string in 'multifile': " + s)

    def buildModel(self):
        # build the model that the list view uses
        self.model = QtGui.QStandardItemModel(self.filelist)
        for x in self.allFiles:
            add = True
            for f in self.method.namefilters:
                if f not in x:
                    add = False  # only add a file if all the filters are present
                    break
            if add:
                # create a checkable item for each file, and check the checkbox
                # if it is in the files list
                item = QtGui.QStandardItem(x)
                item.setCheckable(True)
                if x in self.method.files:
                    item.setCheckState(PyQt5.QtCore.Qt.Checked)
                self.model.appendRow(item)

        self.filelist.setModel(self.model)
        self.model.dataChanged.connect(self.checkedChanged)

    def itemActivated(self, idx):
        # called when we "activate" an item, typically by doubleclicking: load the file
        # to preview it
        item = self.model.itemFromIndex(idx)
        path = os.path.join(self.method.dir, item.text())
        self.method.compileRegex()
        img = ImageCube.load(path, self.method.mapping, None)  # RGB image, null sources
        img.img *= self.method.mult
        self.activatedImagePath = path
        self.activatedImage = img
        self.displayActivatedImage()

    def displayActivatedImage(self):
        if self.activatedImage:
            # we're creating a temporary greyscale image here. We could use an InputSource
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
        self.onInputChanged()  # TODO was self.changed
