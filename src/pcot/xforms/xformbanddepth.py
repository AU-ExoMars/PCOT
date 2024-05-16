from typing import Optional

import numpy as np
from PySide2.QtCore import QSignalBlocker

from pcot.datum import Datum
import pcot.operations as operations
import pcot.ui.tabs
from pcot.imagecube import ImageCube
from pcot.sources import MultiBandSource, SourceSet
from pcot.utils import SignalBlocker
from pcot.value import Value
from pcot.xform import xformtype, XFormType, XFormException


@xformtype
class XformBandDepth(XFormType):
    """
    Calculate band depth using a linear weighted mean of the two bands either side.
    Reference: "Revised CRISM spectral parameters... " Viviano, Seelos et al. 2015.

    Issues:

    * Ignores FWHM (bandwidth) of all bands.
    * can't do weird stuff like Figs. 7c and 7d in the Viviano et al.

    """

    def __init__(self):
        super().__init__("banddepth", "processing", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)
        self.autoserialise = ('bandidx',)

    def createTab(self, n, w):
        return TabBandDepth(n, w)

    def init(self, node):
        node.bandidx = -1
        node.cwls = []  # tuple of (cwl, index, description) generated in perform

    def perform(self, node):
        img: Optional[ImageCube] = node.getInput(0, Datum.IMG)
        if img is not None:
            node.cwls = []
            for x in range(0, img.channels):
                # TODO Possible problem 1: FWHM is ignored.
                cwl = img.wavelength(x)
                if cwl < 0:
                    raise XFormException('DATA', "Cannot get wavelength for all bands in this image")
                else:
                    node.cwls.append(
                        (cwl, x, img.sources.sourceSets[x].brief(node.graph.doc.settings.captionType))
                    )

            # this will be a list of (wavelength, index, desc) tuples
            node.cwls.sort(key=lambda tt: tt[0])  # sort by wavelen

            if node.bandidx != -1:
                if node.bandidx == 0 or node.bandidx == len(node.cwls) - 1:
                    raise XFormException('DATA', "cannot find band depth of first or last band")
                else:
                    lC, cidx, _ = node.cwls[node.bandidx]  # center wavelength
                    lS, sidx, _ = node.cwls[node.bandidx - 1]  # shorter wavelength
                    lL, lidx, _ = node.cwls[node.bandidx + 1]  # longer wavelength

                    # the parameter t is the interpolation weight - it's 0 if C=S, 1 if C=L, and 0.5 if we're halfway.
                    t = (lC - lS) / (lL - lS)

                    # sidx, cidx and lidx are the three bands we are working with - get the reflectances
                    # and their uncertainties/DQs

                    rS = Value(img.img[:, :, sidx], img.uncertainty[:, :, sidx], img.dq[:, :, sidx])
                    rC = Value(img.img[:, :, cidx], img.uncertainty[:, :, cidx], img.dq[:, :, cidx])
                    rL = Value(img.img[:, :, lidx], img.uncertainty[:, :, lidx], img.dq[:, :, lidx])

                    # get weighted mean, the predicted value.
                    rCStar: Value = (rL * Value(t)) + (rS * Value(1.0 - t))
                    # and find the depth!
                    depth: Value = Value(1.0) - (rC / rCStar)

                    sources = MultiBandSource([SourceSet([
                        img.sources[sidx],
                        img.sources[cidx],
                        img.sources[lidx]
                    ])])

                    out = ImageCube(
                        depth.n,
                        uncertainty=depth.u,
                        dq=depth.dq,
                        sources=sources,
                        rois=img.rois.copy(),
                        defaultMapping=None
                    )
                    out = Datum(Datum.IMG, out)
        else:
            out = None
        node.setOutput(0, out)


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
        # need to repopulate without triggering bandChanged. With a newer version of Pyside2 we could
        # sensibly use QSignalBlocker. NOT WORKING.
        self.w.bandCombo.blockSignals(True)
        self.w.bandCombo.clear()
        self.w.bandCombo.blockSignals(False)

        with SignalBlocker(self.w.bandCombo):
            for (_, _, s) in self.node.cwls:
                self.w.bandCombo.addItem(s)

        if self.node.bandidx >= 0:
            self.w.bandCombo.setCurrentIndex(self.node.bandidx)

        self.w.canvas.setNode(self.node)
        self.w.canvas.display(self.node.img)
