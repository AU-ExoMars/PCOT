import numpy as np
from poetry.console.commands import self

from pcot import ui
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

def process(img, mask, whiten, clip_percent):
    # save the original shape and image
    orig = img
    orig_shape = img.shape

    H,W,D = img.shape

    # flatten from (H,W,D) to (H*W, D)
    img = orig.reshape((-1, D)).astype(np.float64)

    # make the 2D mask a 3D mask the shape of the data
    mask = mask.flatten()
    mask = np.repeat(mask, D).reshape(-1, D)
    # and make a masked array from it, remembering that masks are negated in subimages
    maskedA = np.ma.masked_array(data=img.copy(), mask=~mask)

    # centre the masked data
    mean = maskedA.mean()
    maskedA = np.ma.subtract(maskedA, mean)

    # covariance matrix of just the masked part of the array
    cov = np.ma.cov(maskedA, rowvar=False)
    stddevs = np.sqrt(cov.diagonal()) # we return these

    # eigen decomposition
    eigvals, eigvecs = np.linalg.eigh(cov)

    # sort eigens descending (probably not required?)
    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx]
    eigvecs = eigvecs[:, idx]

    # PCA rotation
    # we need to remove the mask so the mat mul will work.
    A = np.ma.filled(maskedA, 0)
    if np.ma.is_masked(eigvecs):
        raise Exception("Eigenvectors have masked elements")
    eigvecs = np.ma.filled(eigvecs, 0)
    pca = A @ eigvecs

    # DO OTHER STUFF HERE!!!
    if whiten:
        eps = 1e-12     # to avoid zeroes
        D_inv_sqrt = np.diag(1.0 / np.sqrt(eigvals+eps))
        pca = pca @ D_inv_sqrt

    # put the mask back
    pca = np.ma.masked_array(pca, mask=~mask)
    valid = pca.compressed()    # get unmasked elements as a flat array; percentile doesn't work on masked arrays
    lo = np.percentile(valid, clip_percent)
    hi = np.percentile(valid, 100-clip_percent)
    # normalise to that range
    pca = (pca-lo)/(hi-lo)
    # and clip the outliers, which are now outside
    pca = np.clip(pca,0,1)



    # reshape back to image shape and type conversion
    pca = pca.astype(np.float32)
    # paste masked area into original subimage, we do this with flattened version
    # of the images to match the flat mask we made.
    orig = orig.flatten()
    pca = pca.flatten()
    np.putmask(orig, mask, pca)
    return orig.reshape(orig_shape), stddevs, eigvals






@xformtype
class XFormPCA(XFormType):
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
            whiten = ("whiten the result", bool, False),
            clip=("percentile outliers to clip in postprocessing", float, 5.0)
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
                                               node.params.whiten,
                                               node.params.clip)

            # in this case, all channels just come from the union of the sources
            sources = SourceSet(node.inimg.sources.getSources())

            # we build the new DQ by OR-ing all the bands' bits together
            dqval = np.bitwise_or.reduce(subimage.dq, axis=2)
            # and then using that for all new channels
            dq = image.imgmerge([dqval]*node.inimg.channels)
            dq |= pcot.dq.NOUNCERTAINTY     # and we've lost all uncertainty data

            # here we build the raw output, where we paste the subimage into a zero image.
            img = node.inimg.zeros_like()
            sources = MultiBandSource([sources]*node.inimg.channels)
            out = img.modifyWithSub(subimage, newimg, sources=sources, dqv=dq).setMapping(node.mapping)
            pca_out = Datum(Datum.IMG, out)

            # here we build and display the RGB output.
            # Step one is getting the rgb-mapped input image
            img = node.inimg.rgbImage()
            # construct a subimage to modify
            subimage = img.subimage()
            # then extract the bands we want from the PCA output
            bands = node.params.rgbmapping.get()
            # making sure they're in range
            if any([x>=img.channels for x in bands]):
                ui.log(f"Some bands are out of range: {bands}")
            bands = [min(x,img.channels-1) for x in bands]
            newimg = newimg[:,:,bands]

            # and paste that in
            sources = MultiBandSource([sources]*3)
            dq = image.imgmerge([dqval]*3)
            dq |= pcot.dq.NOUNCERTAINTY
            out = img.modifyWithSub(subimage, newimg, sources=sources, dqv=dq).setMapping(node.mapping)
            rgb_out = Datum(Datum.IMG, out)

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
        self.w.clip.valueChanged.connect(self.clipChanged)
        self.onNodeChanged()

    def whitenChanged(self, state):
        self.mark()
        self.node.params.whiten = state
        self.changed()

    def clipChanged(self, v):
        self.node.params.clip = v
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
            self.w.canvas.setNode(self.node)

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
        self.w.clip.setValue(params.clip)


        # hackery here to get the constant because of the xformtype wrapper
        self.w.canvas.display(self.node.getOutput(XFormPCA._cls.OUT_RGB))

        # output
        sf = pcot.config.getint("sigfigs")
        if self.node.stddevs is None:
            self.w.stdDevsText.setText("No data")
            self.w.eigenValsText.setText("No data")
        else:
            s = [f"{i}: {round(self.node.stddevs[i],sf)}" for i in range(len(self.node.stddevs))]
            self.w.stdDevsText.setText("\n".join(s))
            s = [f"{i}: {round(self.node.eigenvals[i],sf)}" for i in range(len(self.node.stddevs))]
            self.w.eigenValsText.setText("\n".join(s))

