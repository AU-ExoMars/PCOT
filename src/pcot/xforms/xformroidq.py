import numpy as np
from PySide2.QtWidgets import QComboBox

import pcot
from pcot import dq
from pcot.datum import Datum
from pcot.rois import ROIPainted
from pcot.sources import nullSourceSet
from pcot.utils import SignalBlocker
from pcot.xform import XFormType, xformtype, XFormException

conditions = ["When all present",  # 0
              "When some present",  # 1
              "When all absent",  # 2
              "When some absent"  # 3
              ]


@xformtype
class XFormROIDQ(XFormType):
    """
    Automatically generate an ROI from DQ bits in a band or in all bands.

    <blockquote style="background-color: #ffd0d0;">
    **WARNING**: the ROI will be generated from DQ data from any bands in this image.
    It can then be applied to any other image or band - but this information is not
    tracked by the source mechanism. This means that some source tracking information
    can be lost. (Issue #68)
    </blockquote>
    """

    def __init__(self):
        super().__init__("roidq", "regions", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("img", Datum.IMG)
        self.addOutputConnector("roi", Datum.ROI)

        self.autoserialise = (
            ('caption', 'unknown'),
            ('captiontop', False),
            ('fontsize', 10),
            ('thickness', 2),
            ('colour', (1, 1, 0)),
            ('drawbg', True),
            ('chan', -2),
            ('dq', int(dq.BAD)),
            ('condition', 1)
        )

    def createTab(self, n, w):
        return TabROIDQ(n, w)

    def init(self, node):
        node.img = None
        node.caption = ''
        node.captiontop = False
        node.fontsize = 10
        node.drawbg = True
        node.thickness = 0
        node.colour = (1, 1, 0)

        node.chan = -2  # ALL bands (-1 is ANY)
        node.dq = 0  # bits we're dealing with
        node.condition = 0

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is not None:
            # we're only looking in the subimage, although we'll impose the resulting ROI on the entire image.
            # We don't want to filter BAD bits out, either
            subimg = img.subimage()
            dqs = subimg.maskedDQ()

            # now we have that data, we need to convert into a single band.

            if img.channels > 1:
                if node.chan == -2:  # ANY bands, so we OR them all together
                    dqs = np.bitwise_or.reduce(dqs, axis=2)
                    sources = img.sources.getSources()  # source for ROI is all bands
                elif node.chan == -1:  # ALL bands, so we AND them together
                    dqs = np.bitwise_and.reduce(dqs, axis=2)
                    sources = img.sources.getSources()  # source for ROI is all bands
                else:  # otherwise it's just some band
                    dqs = dqs[:, :, node.chan]
                    sources = img.sources.sourceSets[node.chan]  # source for ROI is just one band
            else:
                # leave dqs as it is for a 1-channel image
                sources = img.sources.getSources()  # source for ROI is all bands

            # now we perform the actual action
            if node.condition == 0:  # when all bits present
                # Here, we want to the result to be True when each pixel DQ ANDed with the node DQ is the same as the
                # node DQ. We AND to extract the relevant bits.
                res = (dqs & node.dq) == node.dq
            elif node.condition == 1:  # when some bits present
                # The result should be True when the relevant bits associated with the pixel are non zero
                res = (dqs & node.dq) != 0
            elif node.condition == 2:  # when all bits absent
                # The result should be True when the relevant bits are zero
                res = (dqs & node.dq) == 0
            elif node.condition == 3:  # when some bits absent
                # The result should be True when the relevant bits are not the same as the requested bits (the node DQ)
                res = (dqs & node.dq) != node.dq
            else:
                raise XFormException('INTR', f"bad condition in roidq: {node.cond}")

            # now we have a result we need to turn it into an ROI
            roi = ROIPainted(mask=res)
            roi.setContainingImageDimensions(img.w, img.h)
            roi.cropDownWithDraw()

            # here we add the origin of the ROI to the origin of the subimage, because
            # that's what we were working on. What's going on here is that the new ROI
            # is inside the subimage and relative to it, so we need to get the coordinates
            # relative to the whole image.
            if roi.bbrect is not None:
                # the BB rect is None if the ROI has no pixels in it!
                roi.bbrect.x += subimg.bb.x
                roi.bbrect.y += subimg.bb.y

            roi.setDrawProps(node.captiontop, node.colour, node.fontsize, node.thickness, node.drawbg)

            img = img.copy()
            img.rois = [roi]

            node.img = img
            node.roi = roi
            outImgDatum = Datum(Datum.IMG, img)
            outROIDatum = Datum(Datum.ROI, roi, sources=sources)
        else:
            node.img = None
            node.roi = None
            outImgDatum = Datum(Datum.IMG, None, nullSourceSet)
            outROIDatum = Datum(Datum.ROI, None, nullSourceSet)

        node.setOutput(0, outImgDatum)
        node.setOutput(1, outROIDatum)

    def getROIDesc(self, node):
        return "no ROI" if node.roi is None else node.roi.details()

    def getMyROIs(self, node):
        return [node.roi]



class TabROIDQ(pcot.ui.tabs.Tab):
    def __init__(self, node, w):
        super().__init__(w, node, 'tabroidq.ui')
        self.w.fontsize.valueChanged.connect(self.fontSizeChanged)
        self.w.drawbg.stateChanged.connect(self.drawbgChanged)
        self.w.thickness.valueChanged.connect(self.thicknessChanged)
        self.w.caption.textChanged.connect(self.textChanged)
        self.w.colourButton.pressed.connect(self.colourPressed)
        self.w.captionTop.toggled.connect(self.topChanged)

        for s in conditions:
            self.w.whenCombo.addItem(s)

        self.w.chanCombo.currentIndexChanged.connect(self.chanChanged)
        self.w.whenCombo.currentIndexChanged.connect(self.whenChanged)
        self.w.dqbits.changed.connect(self.dqChanged)

        self.dontSetText = False
        # sync tab with node
        self.nodeChanged()

    def chanChanged(self, i):
        self.mark()
        self.node.chan = self.w.chanCombo.currentData()
        self.changed()

    def whenChanged(self, i):
        self.mark()
        self.node.condition = i
        self.changed()

    def dqChanged(self):
        self.mark()
        self.node.dq = self.w.dqbits.bits
        self.changed()

    def drawbgChanged(self, val):
        self.mark()
        self.node.drawbg = (val != 0)
        self.changed()

    def topChanged(self, checked):
        self.mark()
        self.node.captiontop = checked
        self.changed()

    def fontSizeChanged(self, i):
        self.mark()
        self.node.fontsize = i
        self.changed()

    def textChanged(self, t):
        self.mark()
        self.node.caption = t
        # this will cause perform, which will cause onNodeChanged, which will
        # set the text again. We set a flag to stop the text being reset.
        self.dontSetText = True
        self.changed()
        self.dontSetText = False

    def thicknessChanged(self, i):
        self.mark()
        self.node.thickness = i
        self.changed()

    def colourPressed(self):
        col = pcot.utils.colour.colDialog(self.node.colour)
        if col is not None:
            self.mark()
            self.node.colour = col
            self.changed()

    def populateBandList(self):
        """Create a list of band data to go into the combo box"""
        with SignalBlocker(self.w.chanCombo):
            self.w.chanCombo.clear()
            self.w.chanCombo.addItem("Any bands", -1)
            self.w.chanCombo.addItem("All bands", -2)
            if self.node.img is not None:
                chanNames = [s.brief(self.node.graph.doc.settings.captionType) for s in
                             self.node.img.sources.sourceSets]
                for i, desc in enumerate(chanNames):
                    self.w.chanCombo.addItem(desc, i)

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # have to do canvas set up here to handle extreme undo events which change the graph and nodes
        self.w.canvas.setMapping(self.node.mapping)
        self.w.canvas.setGraph(self.node.graph)
        self.w.canvas.setPersister(self.node)
        self.w.canvas.setROINode(self.node)
        self.w.canvas.display(self.node.img)

        if not self.dontSetText:
            self.w.caption.setText(self.node.caption)

        self.w.fontsize.setValue(self.node.fontsize)
        self.w.thickness.setValue(self.node.thickness)
        self.w.captionTop.setChecked(self.node.captiontop)
        self.w.drawbg.setChecked(self.node.drawbg)
        r, g, b = [x * 255 for x in self.node.colour]
        self.w.colourButton.setStyleSheet("background-color:rgb({},{},{})".format(r, g, b))

        self.populateBandList()

        self.w.dqbits.bits = self.node.dq
        self.w.dqbits.setChecksToBits()
        with SignalBlocker(self.w.chanCombo, self.w.whenCombo):
            self.w.chanCombo.setCurrentIndex(self.w.chanCombo.findData(self.node.chan))
            self.w.whenCombo.setCurrentIndex(self.node.condition)
