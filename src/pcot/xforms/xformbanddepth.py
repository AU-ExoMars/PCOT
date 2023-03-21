import numpy as np
from PySide2.QtCore import QSignalBlocker

from pcot.datum import Datum
import pcot.operations as operations
import pcot.ui.tabs
from pcot.imagecube import ImageCube
from pcot.sources import MultiBandSource
from pcot.xform import xformtype, XFormType, XFormException


@xformtype
class XformBandDepth(XFormType):
    """
    Calculate band depth using a linear weighted mean of the two bands either side.

    Issues:

    * Ignores FWHM (bandwidth) of all bands.

    """

    def __init__(self):
        super().__init__("banddepth", "processing", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.hasEnable = True
        self.autoserialise = ('bandidx',)

    def createTab(self, n, w):
        return TabBandDepth(n, w)

    def init(self, node):
        node.bandidx = -1
        node.img = None
        node.freqs = []  # tuple of (freq, description) generated in perform

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            node.freqs = []
            for x in range(0, img.channels):
                # TODO Possible problem 1: FWHM is ignored.
                freq = img.wavelength(x)
                if freq < 0:
                    raise XFormException('DATA', "Cannot get wavelength for all bands in this image")
                else:
                    node.freqs.append(
                        (freq, img.sources.sourceSets[x].brief(node.graph.doc.settings.captionType))
                    )
            node.freqs.sort(key=lambda t: t[0])  # sort by freq
            if node.bandidx != -1:
                if node.bandidx == 0 or node.bandidx == len(node.freqs) - 1:
                    raise XFormException('DATA', "cannot find band depth of first or last band")
                else:
                    lo = node.bandidx - 1
                    hi = node.bandidx + 1
                    sources = MultiBandSource([
                        img.sources[lo],
                        img.sources[node.bandidx],
                        img.sources[hi]
                    ])

                    # Lo, Me and Hi are the three bands we are working with
                    imgLo = img.img[:,:,lo]
                    imgMe = img.img[:,:,node.bandidx]
                    imgHi = img.img[:,:,hi]

                    fLo = node.freqs[lo][0]
                    fMe = node.freqs[node.bandidx][0]
                    fHi = node.freqs[hi][0]

                    # the parameter t is the weight - it's 0 if Lo=Me, 1 if Hi=Me, and 0.5 if we're halfway.
                    t = (fMe-fLo)/(fHi-fLo)

                    # get weighted mean
                    mean = (imgHi*t) + (imgLo*(1-t))
                    # and find the depth!
                    depth = mean-imgMe

                    out = ImageCube(
                        depth,
                        sources=sources,
                        rois=img.rois.copy(),
                        defaultMapping=None,
                        uncertainty=None,  # TODO
                        dq=None  # TODO (merge the three channels)
                    )
                    node.img = out
        else:
            node.img = None


class TabBandDepth(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabbanddepth.ui')
        self.w.bandCombo.currentIndexChanged.connect(self.bandChanged)
        self.nodeChanged()

    def bandChanged(self, i):
        self.mark()
        self.node.bandidx = i
        self.changed()

    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)

        # need to repopulate without triggering bandChanged. With a newer version of Pyside2 we could
        # sensibly use QSignalBlocker. NOT WORKING.
        self.w.bandCombo.blockSignals(True)
        self.w.bandCombo.clear()

        for (_, s) in self.node.freqs:
            self.w.bandCombo.addItem(s)

        if self.node.bandidx >= 0:
            self.w.bandCombo.setCurrentIndex(self.node.bandidx)
        self.w.bandCombo.blockSignals(False)

        self.w.canvas.display(self.node.img)
