import re, os
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt, QDir

import cv2 as cv
import numpy as np

import ui, ui.tabs, ui.canvas
from xform import xformtype, XFormType, XFormException
from pancamimage import ImageCube
from channelsource import FileChannelSource

IMAGETYPERE = re.compile(r".*\.(?i:jpg|png|ppm|tga|tif)")


@xformtype
class XFormMultiFile(XFormType):
    """Load multiple image files into greyscale channels"""

    def __init__(self):
        super().__init__("multifile", "source", "0.0.0")
        self.autoserialise = ('namefilters', 'dir', 'files', 'mult', 'filterpat', 'camera')
        self.addOutputConnector("", "img")

    def createTab(self, n, w):
        return TabMultiFile(n, w)

    def init(self, node):
        # list of filter strings - strings which must be in any filenames
        node.namefilters = []
        # directory we're looking at
        node.dir = '.'
        # files we have checked in the file list
        node.files = []
        # all data in all channels is multiplied by this (used for, say, 10 bit images)
        node.mult = 1
        node.camera = "PANCAM"
        node.filterpat = r'.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*'
        node.filterre = None
        # dict of files we currently have, fullpath -> imagecube
        node.cachedFiles = {}

    @staticmethod
    def getFilterName(node, path):
        if node.filterre is None:
            return None
        else:
            m = node.filterre.match(path).groupdict()
            lens = m['lens'] if 'lens' in m else ''
            n = m['n'] if 'n' in m else ''
            return lens + n

    @staticmethod
    def compileRegex(node):
        # compile the regexp that gets the filter ID out.
        try:
            node.filterre = re.compile(node.filterpat)
        except re.error:
            node.filterre = None

    def perform(self, node):
        self.compileRegex(node)

        sources = []  # array of source sets for each image
        imgs = []  # array of actual images (greyscale, numpy)
        newCachedFiles = {}  # will replace the old cache data
        # perform takes all the images in the outputs and bundles them into a single image.
        # They all have to be the same size, and they're all converted to greyscale.
        for i in range(len(node.files)):
            if node.files[i] is not None:
                # we use the relative path here, it's more right that using the absolute path
                # most of the time.
                path = os.path.relpath(os.path.join(node.dir, node.files[i]))
                # build sources data : filename and filter name
                source = {FileChannelSource(path, self.getFilterName(node, path), node.camera == 'AUPE')}
                # is it in the cache?
                if path in node.cachedFiles:
                    img = node.cachedFiles[path]
                else:
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
        node.cachedFiles = newCachedFiles
        # assemble the images - cv.merge can cope with non-3 channels
        if len(imgs) > 0:
            img = cv.merge(imgs)
        else:
            raise XFormException('CTRL', 'No images specified in multifile')
        img = ImageCube(img * node.mult, node.mapping, sources)
        node.setOutput(0, img)


class TabMultiFile(ui.tabs.Tab):
    def __init__(self, node, w):
        self.model = None
        super().__init__(w, node, 'assets/tabmultifile.ui')

        self.w.getinitial.clicked.connect(self.getInitial)
        self.w.filters.textChanged.connect(self.filtersChanged)
        self.w.filelist.activated.connect(self.itemActivated)
        self.w.filterpat.editingFinished.connect(self.patChanged)
        self.w.mult.currentTextChanged.connect(self.multChanged)
        self.w.camCombo.currentIndexChanged.connect(self.cameraChanged)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)

        self.w.canvas.hideMapping()

        # these record the image last clicked on - we need to do that so we can
        # regenerate it with new sources if the camera setting is change.d

        self.activatedImagePath = None
        self.activatedImage = None

        # all the files in the current directory (which match the filters)
        self.allFiles = []
        self.onNodeChanged()

    def cameraChanged(self, i):
        if i == 0:
            self.node.camera = "PANCAM"
        else:
            self.node.camera = "AUPE"
        self.changed()

    def getInitial(self):
        # select a directory
        res = QtWidgets.QFileDialog.getExistingDirectory(None, 'Directory for images', '.')
        if res != '':
            self.selectDir(res)

    def selectDir(self, dir):
        # called when we want to load a new directory, or when the node has changed (on loading)
        if self.node.dir != dir:  # if the directory has changed reset the selected file list
            self.node.files = []
            self.node.type.clearImages(self.node)
        self.w.dir.setText(dir)
        # get all the files in dir which are images
        self.allFiles = sorted([f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))
                                and IMAGETYPERE.match(f) is not None])
        # using the relative path (usually more right than using the absolute)
        self.node.dir = os.path.relpath(dir)
        # rebuild the model
        self.buildModel()

    def patChanged(self):
        self.node.filterpat = self.w.filterpat.text()
        self.changed()

    def filtersChanged(self, t):
        # rebuild the filter list from the comma-sep string and rebuild the model
        self.node.namefilters = t.split(",")
        self.buildModel()

    def multChanged(self, s):
        try:
            self.node.mult = float(s)
            self.changed()
        except (ValueError, OverflowError):
            raise XFormException("CTRL", "Bad mult string in 'multifile': " + s)

    def onNodeChanged(self):
        # the node has changed - set the filters text widget and reselect the dir.
        # This will only clear the selected files if we changed the dir.
        self.w.filters.setText(",".join(self.node.namefilters))
        self.selectDir(self.node.dir)
        s = ""
        for i in range(len(self.node.files)):
            s += "{}:\t{}\n".format(i, self.node.files[i])
        #        s+="\n".join([str(x) for x in self.node.imgpaths])
        self.w.outputFiles.setPlainText(s)
        i = self.w.mult.findText(str(int(self.node.mult)))
        self.w.mult.setCurrentIndex(i)
        self.w.filterpat.setText(self.node.filterpat)
        if self.node.camera == 'AUPE':
            self.w.camCombo.setCurrentIndex(1)
        else:
            self.w.camCombo.setCurrentIndex(0)
        self.displayActivatedImage()

    def buildModel(self):
        # build the model that the list view uses
        self.model = QtGui.QStandardItemModel(self.w.filelist)
        for x in self.allFiles:
            add = True
            for f in self.node.namefilters:
                if f not in x:
                    add = False  # only add a file if all the filters are present
                    break
            if add:
                # create a checkable item for each file, and check the checkbox
                # if it is in the files list
                item = QtGui.QStandardItem(x)
                item.setCheckable(True)
                if x in self.node.files:
                    item.setCheckState(Qt.Checked)
                self.model.appendRow(item)

        self.w.filelist.setModel(self.model)
        self.model.dataChanged.connect(self.checkedChanged)

    def itemActivated(self, idx):
        # called when we "activate" an item, typically by doubleclicking: load the file
        # to preview it
        item = self.model.itemFromIndex(idx)
        path = os.path.join(self.node.dir, item.text())
        self.node.type.compileRegex(self.node)
        img = ImageCube.load(path, self.node.mapping, None)  # RGB image
        img.img *= self.node.mult
        self.activatedImagePath = path
        self.activatedImage = img
        self.displayActivatedImage()

    def displayActivatedImage(self):
        if self.activatedImage:
            source = {FileChannelSource(self.activatedImagePath,
                                        self.node.type.getFilterName(self.node, self.activatedImagePath),
                                        self.node.camera == 'AUPE')}
            self.activatedImage.sources = [source, source, source]
            self.w.canvas.display(self.activatedImage)

    def checkedChanged(self):
        # the checked items have changed, reset the list and regenerate
        # the files list
        self.node.files = []
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.checkState() == Qt.Checked:
                self.node.files.append(item.text())
        self.changed()
