## the Multifile input method, inputting several greyscale images
# into a single image
import logging
import os
import re
from typing import Tuple

import PySide2
from PySide2 import QtWidgets, QtGui
from PySide2.QtCore import Qt

import pcot
from .inputmethod import InputMethod
from pcot.imagecube import ChannelMapping, ImageCube
from pcot.ui.canvas import Canvas
from pcot.ui.inputs import MethodWidget
from .. import ui
from ..datum import Datum
from ..filters import getFilterSetNames, getFilter
from ..sources import InputSource, SourceSet, MultiBandSource
from ..ui import uiloader
from ..utils import image

logger = logging.getLogger(__name__)


class MultifileInputMethod(InputMethod):
    """
    This turns a set of files into a single image. It pulls data out of the filename which it uses to lookup
    into a set of filter objects.

    How this works:

        * filterset determines the name of the filter set to use (typically PANCAM or AUPE but more can be added)
        * filterpat determines how the name is used to look up a filter in the set. It's a
          regex (regular expression).
            * If the filterpat contains ?P<lens> and ?P<n>, then lens+n is used to look up the filter by position.
              For example lens=L and n=01 would look up L01 in the filter position
            * Otherwise if the filterpat contains ?<name>, then name is used to look up the filter by name.
            * Otherwise if the filterpat contains ?<cwl>, then cwl is used to look up the filter's wavelength.

        If none of this works a dummy filter is returned.

    """
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
        self.filterset = "PANCAM"
        self.defaultLens = "L"
        self.filterpat = r'.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*'
        self.filterre = None
        # dict of files we currently have, fullpath -> imagecube
        self.cachedFiles = {}

        self.mapping = ChannelMapping()

    def long(self):
        lst = [f"{i}: {f}" for i, f in enumerate(self.files)]
        return f"MULTI: path={self.dir} {', '.join(lst)}]"

    def getFilterSearchParam(self, path) -> Tuple[str,str]:
        """Returns the thing to search for to match a filter to a path and the type of the search"""
        if self.filterre is None:
            return None, None
        else:
            m = self.filterre.match(path)
            if m is None:
                return None, None
            m = m.groupdict()
            if '<lens>' in self.filterpat:
                if '<n>' not in self.filterpat:
                    raise Exception(f"A filter with <lens> must also have <n>")
                # lens is either left or right
                lens = m.get('lens', '')
                n = m.get('n', '')
                return lens + n, 'pos'
            elif '<name>' in self.filterpat:
                return m.get('name', ''), 'name'
            elif '<cwl>' in self.filterpat:
                return int(m.get('cwl', '0')), 'cwl'

    def compileRegex(self):
        # compile the regexp that gets the filter ID out.
        logger.info(f"Compiling RE: {self.filterpat}")
        try:
            self.filterre = re.compile(self.filterpat)
        except re.error:
            self.filterre = None
            logger.error("Cannot compile RE!!!!")

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

                # Now read the file - we do this before building source data because any exceptions raised
                # here are more important.
                #
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
                        c = image.imgsplit(img.img)[0]  # just use channel 0
                        img = ImageCube(c, None, None)

                # build sources data - this will use the filter, which we'll extract from the filename.
                filtpos, searchtype = self.getFilterSearchParam(path)
                filt = getFilter(self.filterset, filtpos, searchtype)
                source = InputSource(self, filt)

                # store in cache
                newCachedFiles[path] = img
                imgs.append(img.img)  # store numpy image
                sources.append(source)

        # replace the old cache dict with the new one we have built
        self.cachedFiles = newCachedFiles
        # assemble the images
        if len(imgs) > 0:
            if len(set([x.shape for x in imgs])) != 1:
                raise Exception("all images must be the same size in a multifile")
            img = image.imgmerge(imgs)
            self.mapping.red = -1  # force repeat of "guessing" of RGB mapping
            img = ImageCube(img * self.mult, self.mapping, MultiBandSource(sources))
        else:
            img = None
        return Datum(Datum.IMG, img)

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
        x = {'namefilters': self.namefilters,
             'dir': self.dir,
             'files': self.files,
             'mult': self.mult,
             'filterpat': self.filterpat,
             'filterset': self.filterset,
             'defaultlens': self.defaultLens
             }
        if internal:
            x['cache'] = self.cachedFiles

        Canvas.serialise(self, x)
        return x

    def deserialise(self, data, internal):
        self.namefilters = data['namefilters']
        self.dir = data['dir']
        self.files = data['files']
        self.mult = data['mult']
        self.filterpat = data['filterpat']

        # deal with legacy files where "filterset" is called "camera"
        if 'filterset' in data:
            self.filterset = data['filterset']
        else:
            self.filterset = data['camera']

        self.defaultLens = data.get('defaultlens', 'L')
        if internal:
            self.cachedFiles = data['cache']

        Canvas.deserialise(self, data)


# Then the UI class..


IMAGETYPERE = re.compile(r".*\.(?i:jpg|bmp|png|ppm|tga|tif)")


class MultifileMethodWidget(MethodWidget):
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
        self.filters.textChanged.connect(self.filtersChanged)
        self.filelist.activated.connect(self.itemActivated)
        self.filterpat.editingFinished.connect(self.patChanged)
        self.defaultLens.currentTextChanged.connect(self.defaultLensChanged)
        self.mult.currentTextChanged.connect(self.multChanged)
        self.filtSetCombo.currentIndexChanged.connect(self.filterSetChanged)
        self.canvas.setMapping(m.mapping)
        # self.canvas.hideMapping()  # because we're showing greyscale for each image
        self.canvas.setGraph(self.method.input.mgr.doc.graph)
        self.canvas.setPersister(m)

        self.filelist.setMinimumWidth(300)
        self.setMinimumSize(1000, 500)

        self.filtSetCombo.addItems(getFilterSetNames())

        if self.method.dir is None or len(self.method.dir)==0:
            self.method.dir = pcot.config.getDefaultDir('images')
        self.onInputChanged()

    def filterSetChanged(self, i):
        self.method.filterset = self.filtSetCombo.currentText()
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
        i = self.mult.findText(str(int(self.method.mult)) + ' ', Qt.MatchFlag.MatchStartsWith)
        self.mult.setCurrentIndex(i)
        self.filterpat.setText(self.method.filterpat)
        i = self.defaultLens.findText(self.method.defaultLens, Qt.MatchFlag.MatchStartsWith)
        self.defaultLens.setCurrentIndex(i)
        # this won't work if the filter set isn't in the combobox.
        self.filtSetCombo.setCurrentText(self.method.filterset)
        self.displayActivatedImage()
        self.invalidate()  # input has changed, invalidate so the cache is dirtied
        # we don't do this when the window is opening, otherwise it happens a lot!
        if not self.method.openingWindow:
            self.method.input.performGraph()
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

    def filtersChanged(self, t):
        # rebuild the filter list from the comma-sep string and rebuild the model
        self.method.namefilters = t.split(",")
        self.buildModel()

    def multChanged(self, s):
        try:
            # strings in the combobox are typically "64 (6 bit shift)"
            ll = s.split()
            if len(ll) > 0:
                self.method.mult = float(ll[0])
                self.onInputChanged()  # TODO was self.changed
        except (ValueError, OverflowError):
            raise Exception("CTRL", "Bad mult string in 'multifile': " + s)

    def defaultLensChanged(self, s):
        self.method.defaultLens = s[0] # just first character

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
