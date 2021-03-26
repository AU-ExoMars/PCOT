import cv2 as cv
import numpy as np
from PyQt5 import QtGui, QtWidgets

import conntypes
import ui.number
import ui.tabs
from pancamimage import ImageCube
from utils import binop
from xform import xformtype, XFormType, XFormException, Datum


class XFormBinop(XFormType):

    def __init__(self, name):
        super().__init__(name, "maths", "0.0.0")
        self.addInputConnector("", conntypes.ANY)
        self.addInputConnector("", conntypes.ANY)
        self.addOutputConnector("", conntypes.VARIANT)

    def createTab(self, n, w):
        return TabBinop(n, w)

    def init(self, node):
        pass

    def perform(self, node):
        a = node.getInput(0)
        b = node.getInput(1)

        res = binop.binop(a, b, self.op, node.getOutputType(0))
        if res is not None and res.isImage():
            res.val.setMapping(node.mapping)
            node.img = res.val
        else:
            node.img = None
        node.setOutput(0, res)

    def OLDperform(self, node):
        img1 = node.getInput(0)
        img2 = node.getInput(1)

        if img1 is None and img2 is None:
            img = None
        else:
            # having the RGB mapping and more particularly the sources as empty here might cause problems?
            if img1 is None:
                img1 = ImageCube(np.zeros(img2.img.shape, dtype=np.float32))
            elif img2 is None:
                img2 = ImageCube(np.zeros(img1.img.shape, dtype=np.float32))

            if img1.channels != img2.channels:
                img = None
                node.setError(XFormException('DATA', 'channel count mismatch'))
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
                # here I set the mapping up for the output
                img.setMapping(node.mapping)
                img.sources = sources
        node.img = img
        node.setOutput(0, Datum(conntypes.IMG, img))

        # TODO - ROIs


@xformtype
class XFormAdd(XFormBinop):
    def __init__(self):
        super().__init__("add")
        self.op = lambda x, y: x+y


@xformtype
class XFormSub(XFormBinop):
    def __init__(self):
        super().__init__("subtract")
        self.op = lambda x, y: x-y


@xformtype
class XFormMul(XFormBinop):
    def __init__(self):
        super().__init__("multiply")
        self.op = lambda x, y: x*y


@xformtype
class XFormDiv(XFormBinop):
    def __init__(self):
        super().__init__("divide")
        self.op = lambda x, y: x/y


class TabBinop(ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'assets/tabbinop.ui')
        # populate with types
        layout = QtWidgets.QVBoxLayout()
        self.buttons = []
        idx = 0
        for x in conntypes.types:
            b = QtWidgets.QRadioButton(x)
            layout.addWidget(b)
            self.buttons.append(b)
            b.idx = idx
            idx += 1
            b.toggled.connect(self.buttonToggled)
        self.w.canvas.setMapping(node.mapping)
        self.w.canvas.setGraph(node.graph)
        self.w.type.setLayout(layout)
        self.onNodeChanged()

    def onNodeChanged(self):
        # set the current type
        i = conntypes.types.index(self.node.getOutputType(0))
        self.buttons[i].setChecked(True)
        self.w.canvas.display(self.node.img)

    def buttonToggled(self, checked):
        for b in self.buttons:
            if b.isChecked():
                self.node.outputTypes[0] = conntypes.types[b.idx]
                self.node.graph.ensureConnectionsValid()
                self.changed()
                break
