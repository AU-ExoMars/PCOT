import numpy as np

import pcot.dq
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.sources import MultiBandSource, SourceSet
from pcot.ui.tabs import Tab
from pcot.utils import image
from pcot.value import Value
from pcot.xform import xformtype, XFormType, XFormException


@xformtype
class XformDecorr(XFormType):
    """
    Perform a decorrelation stretch on an RGB image by applying a whitening transform
    with stretch.

    This works by

    * calculating the covariance matrix
    * calculating a transform to a space in which the diagonals of the covariance matrix are 1 and the
      other elements are minimised (i.e. the bands are decorrelated) - so this is a form of PCA
    * applying that transform
    * applying a stretch factor to increase those diagonal variances - the principal components
    * apply the inverse transform
    * restore original image scaling
    * fix up the image mean
    * normalise each band after clipping a given percentile of outliers

    **Ignores DQ and uncertainty**

    """

    def __init__(self):
        super().__init__("decorr stretch", "processing", "0.0.0", hasEnable=False)
        self.addInputConnector("rgb", Datum.IMG)
        self.addOutputConnector("rgb", Datum.IMG)
        self.addOutputConnector("eigs", Datum.NUMBER)
        self.addOutputConnector("sds", Datum.NUMBER)
        self.params = TaggedDictType(
            stretch=("stretch factor", float, 1.0),
            clip=("percentile outliers to clip in postprocessing", float, 5.0))

    def createTab(self, n, w):
        return TabDecorr(n, w)

    def init(self, node):
        node.out = None
        node.eigenvals = None
        node.stddevs = None

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)
        if img is None:
            out = None
            eigvals = None
            stddevs = None
            eigsout = Datum.null
            stdsout = Datum.null
#        elif img.channels != 3:
#            raise XFormException("DATA", "can only decorr stretch images with 3 channels")
        else:
            from pcot.utils.decorr import decorrelation_stretch
            subimage = img.subimage()
            newimg, stddevs, eigvals = decorrelation_stretch(subimage.img, subimage.mask,
                                                             node.params.stretch,
                                                             node.params.clip)
            # in this case, all channels just come from the union of the sources
            sources = SourceSet(img.sources.getSources())

            # we build the new DQ by OR-ing all the bands' bits together
            dqval = np.bitwise_or.reduce(subimage.dq, axis=2)
            # and then using that for all new channels
            dq = image.imgmerge([dqval]*img.channels)
            dq |= pcot.dq.NOUNCERTAINTY     # and we've lost all uncertainty data

            out = img.modifyWithSub(subimage, newimg, sources=MultiBandSource([sources]*img.channels), dqv=dq).setMapping(node.mapping)
            out = Datum(Datum.IMG, out)

            # build the unc and dq values for the vector outputs, completely flattening the DQs into a single int
            uncs = np.full(eigvals.shape, 0.0, dtype=np.float32)
            dqval = np.bitwise_or.reduce(dqval, axis=None)
            dqs = np.full(eigvals.shape, dqval, dtype=np.uint16)
            # and the values themselves
            eigsout = Datum(Datum.NUMBER, Value(eigvals, uncs, dqs), sources=sources)
            stdsout = Datum(Datum.NUMBER, Value(stddevs, uncs, dqs), sources=sources)

        node.eigenvals = eigvals
        node.stddevs = stddevs
        node.setOutput(0, out)
        node.setOutput(1, eigsout)
        node.setOutput(2, stdsout)

class TabDecorr(Tab):
    def __init__(self, node, w):
        super().__init__(w, node, "tabdecorr.ui")
        self.w.stretchSpin.valueChanged.connect(self.stretchChanged)
        self.w.clipSpin.valueChanged.connect(self.clipChanged)

        self.nodeChanged()

    def stretchChanged(self, v):
        self.node.params.stretch = v
        self.changed()

    def clipChanged(self, v):
        self.node.params.clip = v
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        p = self.node.params

        self.w.stretchSpin.setValue(p.stretch)
        self.w.clipSpin.setValue(p.clip)
        sf = pcot.config.getint("sigfigs")

        if self.node.stddevs is None:
            self.w.stdDevsText.setText("No data")
            self.w.eigenValsText.setText("No data")
        else:
            s = [f"{i}: {round(self.node.stddevs[i],sf)}" for i in range(len(self.node.stddevs))]
            self.w.stdDevsText.setText("\n".join(s))
            s = [f"{i}: {round(self.node.eigenvals[i],sf)}" for i in range(len(self.node.stddevs))]
            self.w.eigenValsText.setText("\n".join(s))


        self.w.canvas.display(self.node.getOutput(0))