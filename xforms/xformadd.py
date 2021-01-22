from PyQt5 import QtCore, QtGui
import cv2 as cv
import numpy as np

import ui, ui.tabs, ui.canvas, ui.number
from xform import xformtype, XFormType
from xforms.tabimage import TabImage
from pancamimage import ImageCube


@xformtype
class XFormAdd(XFormType):
    """Add two images, optionally multiplying each by a constant and adding a constant.
    The output may be optionally clipped or normalized, either to the calculated range
    of the result or to the range of the output image. Both images must have the same
    depth. The second image will be resized to match first image size if they are different
    sizes."""

    def __init__(self):
        super().__init__("add", "maths", "0.0.0")
        self.addInputConnector("", "img")
        self.addInputConnector("", "img")
        self.addOutputConnector("", "img")
        self.autoserialise = ('k', 'm1', 'm2', 'postproc')

    def createTab(self, n, w):
        return TabMaths(n, w)

    def generateOutputTypes(self, node):
        # here, the output type matches input 0
        node.matchOutputsToInputs([(0, 0)])

    def init(self, node):
        node.m1 = 1
        node.m2 = 1
        node.k = 0
        node.postproc = 0
        node.img = None

    def perform(self, node):
        img1 = node.getInput(0)
        img2 = node.getInput(1)

        if img1 is None and img2 is None:
            img = None
        else:
            if img1 is None:
                img1 = ImageCube(np.zeros(img2.img.shape, dtype=np.float32))
            elif img2 is None:
                img2 = ImageCube(np.zeros(img1.img.shape, dtype=np.float32))

            if img1.channels != img2.channels:
                img = None
            else:
                # we only use the ROI on image 1 but we use it to cut out the image
                # on img 2. The images will be the same size.
                subimage1 = img1.subimage()
                i1 = subimage1.img
                i2 = img2.img
                # cut out that second image using the ROI from image 1.
                i2 = subimage1.cropother(img2).img

                if i1.shape[:2] != i2.shape[:2]:
                    h, w = i1.shape[:2]
                    i2 = cv.resize(i2, (w, h))

                img = i1 * node.m1 + i2 * node.m2 + node.k

                # the sources for each channel get messy here, because each channel can now come from
                # multiple sources.
                sources = ImageCube.buildSources([img1, img2])

                # postprocess, normalising and clipping but only to the mask in subimage1
                if node.postproc == 0:  # clip
                    mask = ~subimage1.fullmask()
                    masked = np.ma.masked_array(data=img, mask=mask)
                    masked[masked > 1] = 1
                    masked[masked < 0] = 0
                    np.putmask(img, ~mask, masked)
                elif node.postproc == 1:  # norm to output
                    mask = ~subimage1.fullmask()
                    masked = np.ma.masked_array(data=img, mask=mask)
                    # calculate the output range
                    mn = node.k
                    mx = node.m1 + node.m2 + node.k
                    masked = (masked - mn) / (mx - mn)
                    np.putmask(img, ~mask, masked)
                elif node.postproc == 2:  # norm to image max across all channels
                    mask = ~subimage1.fullmask()
                    masked = np.ma.masked_array(data=img, mask=mask)
                    mx = masked.max()
                    mn = masked.min()
                    masked = (masked - mn) / (mx - mn)
                    np.putmask(img, ~mask, masked)
                elif node.postproc == 3:  # do nothing to it
                    pass

                # apply the result to the subimage region for image 1
                img = img1.modifyWithSub(subimage1, img)
                img.sources = sources
        node.img = img
        node.setOutput(0, img)

        # TODO - ROIs


class TabMaths(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabadd.ui')
        self.w.m1.setValidator(QtGui.QDoubleValidator())
        self.w.m2.setValidator(QtGui.QDoubleValidator())
        self.w.k.setValidator(QtGui.QDoubleValidator())

        self.w.m1.editingFinished.connect(self.m1Changed)
        self.w.m2.editingFinished.connect(self.m2Changed)
        self.w.k.editingFinished.connect(self.kChanged)

        self.w.postproc.currentIndexChanged.connect(self.postprocChanged)

        self.onNodeChanged()

    def m1Changed(self):
        self.node.m1 = float(self.w.m1.text())
        self.changed()

    def m2Changed(self):
        self.node.m2 = float(self.w.m2.text())
        self.changed()

    def postprocChanged(self, i):
        self.node.postproc = i
        self.changed()

    def kChanged(self):
        self.node.k = float(self.w.k.text())
        self.changed()

    def onNodeChanged(self):
        self.w.m1.setText(str(self.node.m1))
        self.w.m2.setText(str(self.node.m2))
        self.w.k.setText(str(self.node.k))
        self.w.postproc.setCurrentIndex(self.node.postproc)
        self.w.canvas.display(self.node.img)
