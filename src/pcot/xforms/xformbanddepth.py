import numpy as np
from PySide2.QtCore import QSignalBlocker

from pcot.datum import Datum
import pcot.operations as operations
import pcot.ui.tabs
from pcot.imagecube import ImageCube
from pcot.sources import MultiBandSource
from pcot.utils import SignalBlocker
from pcot.xform import xformtype, XFormType, XFormException


@xformtype
class XformBandDepth(XFormType):
    """
    Calculate band depth using a linear weighted mean of the two bands either side.
    Reference: "Revised CRISM spectral parameters... " Viviano, Seelos et al. 2015.

    Issues:

    * Ignores FWHM (bandwidth) of all bands.
    * No uncertainty
    * can't do weird stuff like Figs. 7c and 7d in the Viviano et al.

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
        node.cwls = []  # tuple of (cwl, description) generated in perform

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            node.cwls = []
            for x in range(0, img.channels):
                # TODO Possible problem 1: FWHM is ignored.
                cwl = img.wavelength(x)
                if cwl < 0:
                    raise XFormException('DATA', "Cannot get wavelength for all bands in this image")
                else:
                    node.cwls.append(
                        (cwl, img.sources.sourceSets[x].brief(node.graph.doc.settings.captionType))
                    )
            node.cwls.sort(key=lambda t: t[0])  # sort by wavelen
            if node.bandidx != -1:
                if node.bandidx == 0 or node.bandidx == len(node.cwls) - 1:
                    raise XFormException('DATA', "cannot find band depth of first or last band")
                else:
                    sidx = node.bandidx - 1  # shorter wavelength
                    lidx = node.bandidx + 1  # longer wavelength
                    sources = MultiBandSource([
                        img.sources[sidx],
                        img.sources[node.bandidx],
                        img.sources[lidx]
                    ])

                    # sidx, bandidx and lidx are the three bands we are working with - get the reflectances
                    rS = img.img[:, :, sidx]
                    rC = img.img[:, :, node.bandidx]
                    rL = img.img[:, :, lidx]

                    # get wavelengths
                    lS = node.cwls[sidx][0]
                    lC = node.cwls[node.bandidx][0]
                    lL = node.cwls[lidx][0]

                    # the parameter t is the weight - it's 0 if Lo=Me, 1 if Hi=Me, and 0.5 if we're halfway.
                    t = (lC - lS) / (lL - lS)

                    # get weighted mean, the predicted value.
                    rCStar = (rL * t) + (rS * (1 - t))
                    # and find the depth!
                    depth = 1 - (rC / rCStar)

                    dq = np.bitwise_or.reduce(img.dq, axis=2)

                    out = ImageCube(
                        depth,
                        sources=sources,
                        rois=img.rois.copy(),
                        defaultMapping=None,
                        uncertainty=None,  # TODO (or not).
                        dq=dq
                    )
                    node.img = out
                    node.setOutput(0, Datum(Datum.IMG, out))
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
        self.w.bandCombo.blockSignals(False)

        with SignalBlocker(self.w.bandCombo):
            for (_, s) in self.node.cwls:
                self.w.bandCombo.addItem(s)
            if self.node.bandidx >= 0:
                self.w.bandCombo.setCurrentIndex(self.node.bandidx)

        self.w.canvas.display(self.node.img)
