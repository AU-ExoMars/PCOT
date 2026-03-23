import numpy as np

from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType
from pcot.sources import MultiBandSource, SourceSet
from pcot.ui.tabs import Tab
from pcot.utils import SignalBlocker, image
from pcot.utils.decorr import decorrelation_stretch
from pcot.value import Value
from pcot.xform import xformtype, XFormType
import pcot.dq

import logging
logger = logging.getLogger(__name__)

def process(img, mask, whiten):
    # PLACEHOLDER
    return decorrelation_stretch(img, mask, 1)


@xformtype
class XformPCA(XFormType):
    """
    Perform a principal component analysis and optionally a whitening transform

    **Ignores DQ and uncertainty**

    """

    OUT_RGB = 0
    OUT_PCA = 1
    OUT_EIGS = 2
    OUT_SDS = 3

    def __init__(self):
        super().__init__("PCA", "processing", "0.0.0", hasEnable=False)
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("rgb", Datum.IMG)
        self.addOutputConnector("PCA", Datum.IMG)
        self.addOutputConnector("eigs", Datum.NUMBER)
        self.addOutputConnector("sds", Datum.NUMBER)
        self.params = TaggedDictType(
            rgbmapping = ("rgb mapping", TaggedListType(int,[0,1,2], 0)),
            whiten = ("whiten the result", bool, False)
        )


    def createTab(self, n, w):
        return TabPCA(n, w)

    def init(self, node):
        node.inimg = None

    def perform(self, node):
        node.inimg = node.getInput(0, Datum.IMG)
        if node.inimg is None:
            eigvals = None
            stddevs = None
            eigsout = Datum.null
            stdsout = Datum.null
            rgb_out = Datum.null
            pca_out = Datum.null
        else:
            subimage = node.inimg.subimage()
            newimg, stddevs, eigvals = process(subimage.img, subimage.mask,
                                               node.params.whiten)

            # in this case, all channels just come from the union of the sources
            sources = SourceSet(node.inimg.sources.getSources())

            # we build the new DQ by OR-ing all the bands' bits together
            dqval = np.bitwise_or.reduce(subimage.dq, axis=2)
            # and then using that for all new channels
            dq = image.imgmerge([dqval]*node.inimg.channels)
            dq |= pcot.dq.NOUNCERTAINTY     # and we've lost all uncertainty data

            # here we build the raw output.
            img = node.inimg.copy()
            sources = MultiBandSource([sources]*node.inimg.channels)
            out = img.modifyWithSub(subimage, newimg, sources=sources, dqv=dq).setMapping(node.mapping)
            pca_out = Datum(Datum.IMG, out)

            rgb_out = Datum.null

            # build the unc and dq values for the vector outputs, completely flattening the DQs into a single int
            uncs = np.full(eigvals.shape, 0.0, dtype=np.float32)
            dqval = np.bitwise_or.reduce(dqval, axis=None)
            dqs = np.full(eigvals.shape, dqval, dtype=np.uint16)
            # and the values themselves
            eigsout = Datum(Datum.NUMBER, Value(eigvals, uncs, dqs), sources=sources)
            stdsout = Datum(Datum.NUMBER, Value(stddevs, uncs, dqs), sources=sources)

        node.eigenvals = eigvals
        node.stddevs = stddevs

        node.setOutput(self.OUT_RGB, rgb_out)
        node.setOutput(self.OUT_PCA, pca_out)
        node.setOutput(self.OUT_EIGS, eigsout)
        node.setOutput(self.OUT_SDS, stdsout)



class TabPCA(Tab):
    def __init__(self, n, w):
        super().__init__(w, n, "tabPCA.ui")
        self.w.whiten.toggled.connect(self.whitenChanged)
        self.w.red.currentIndexChanged.connect(lambda v: self.mappingChanged(0,v))
        self.w.green.currentIndexChanged.connect(lambda v: self.mappingChanged(1,v))
        self.w.blue.currentIndexChanged.connect(lambda v: self.mappingChanged(2,v))
        self.onNodeChanged()

    def whitenChanged(self, state):
        self.mark()
        self.node.params.whiten = state
        self.changed()

    def mappingChanged(self, i, v):
        self.mark()
        self.node.params.rgbmapping[i] = v
        self.changed()

    def onNodeChanged(self):
        n = self.node
        params = self.node.params

        # reset the RGB mappings by repopulating and setting the indices

        with SignalBlocker(self.w.red, self.w.green, self.w.blue):
            self.w.red.clear()
            self.w.green.clear()
            self.w.blue.clear()
            if n.inimg is not None:
                bands = [str(x) for x in range(0,n.inimg.channels)]
                self.w.red.addItems(bands)
                self.w.green.addItems(bands)
                self.w.blue.addItems(bands)
                self.w.red.setCurrentIndex(params.rgbmapping[0])
                self.w.green.setCurrentIndex(params.rgbmapping[1])
                self.w.blue.setCurrentIndex(params.rgbmapping[2])

        # other params
        self.w.whiten.setChecked(params.whiten)
