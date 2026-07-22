import numpy as np
from PySide6 import QtCore
from poetry.console.commands import self

from pcot import ui
from pcot.datum import Datum
from pcot.imagecube import SubImageCube
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

def process(subimg: SubImageCube, mode, stretch, clip_percent=5, stretch_factor=None):
    """
    PCA an image and optionally whiten or decorr stretch it. Then optionally normalize and clip a given
    percentage of outliers.

    img: the image to process
    mask: a mask on the image (negated as per subimage use)
    mode: "pca" or "decorr" - determines whether or rotate back into the original colour space
    stretch: whether any "stretching" is applied to the image once it is in PCA space. If so, options are:
        - whiten: apply a whitening transform to the image (divide each PC by its std dev.)
        - stretch: divide each PC by the mean of the PCs, thus scaling each PC to the average variance, boosting weak
          PCs and reducing large PCs.
    normalize: whether to normalize the image afterwards
    clip_percent: the percentile of outliers in the resulting image to clip
    stretch_factors: the stretch to apply to components when doing a decorr stretch; if not provided will
                        stretch by equalising the variances
    """
    # save the original shape and image

    orig = subimg.masked(maskBadPixels=True)
    masked_img = orig.copy()

    orig_shape = masked_img.shape
    H,W,D = orig_shape


    # flatten from (H,W,D) to (H*W, D)
    masked_img = masked_img.reshape((-1, D)).astype(np.float64)

    # centre the masked data
    mean = masked_img.mean()
    maskedA = np.ma.subtract(masked_img, mean)

    # covariance matrix of just the masked part of the array
    cov = np.ma.cov(maskedA, rowvar=False)
    stddevs = np.sqrt(cov.diagonal()) # we return these

    # eigen decomposition
    eigvals, eigvecs = np.linalg.eigh(cov)

    # sort eigens descending (probably not required?)
    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx]
    eigvecs = eigvecs[:, idx]

    # save the mask
    mask = masked_img.mask

    # PCA rotation
    # we need to remove the mask so the mat mul will work.
    A = np.ma.filled(maskedA, 0)
    if np.ma.is_masked(eigvecs):
        raise Exception("Eigenvectors have masked elements")
    eigvecs = np.ma.filled(eigvecs, 0) # this doesn't actually do anything but convert a filled masked array into a normal one
    pca = A @ eigvecs

    # WE ARE NOW IN PCA COORDINATES
    # DO OTHER STUFF HERE!!!

    epsilon = 1e-12  # to avoid zeroes
    if stretch == "stretch":
        # If no stretch is provided, scale the PCs so that they all have the same variance as the mean PC. PCs with a small
        # variance will get boosted, PCs with a large variance will be reduced.
        stretch_factor = eigvals.mean() if stretch_factor is None else stretch_factor
        # each PC has has variance equal to its eigenvalue. Here we divide by the root of that eigenvalue. Why the root?
        # Each PC has a variance var(PC). That's the square of the standard deviation. But this is a vector, and we want to
        # normalise it. Here, the variance is the mean *squared* magnitude of the vector - std dev is the actual length
        # of the PC vector. So to normalise we divide by the root (the standard deviation). So we're normalising to
        # some length.
        stretch_factors = stretch_factor / np.sqrt(eigvals+epsilon)
    elif stretch == "whiten":
        stretch_factors = 1.0 / np.sqrt(eigvals+epsilon)
    elif stretch == "none":
        stretch_factors = np.ones_like(eigvals)
    else:
        raise ValueError(f"Unknown stretch type: {stretch}")

    # apply the stretch
    S = np.diag(stretch_factors)        # stretch transformation
    pca = pca @ S

    if mode == "decorr":
        # rotate back after applying stretch
        pca = pca @ eigvecs.T

    # reapply mask

    pca = np.ma.masked_array(pca, mask=mask)

    if clip_percent > 0:
        valid = pca.compressed()    # get unmasked elements as a flat array; percentile doesn't work on masked arrays
        img_min = np.ma.min(valid)
        img_max = np.ma.max(valid)
        lo = np.percentile(valid, clip_percent)
        hi = np.percentile(valid, 100-clip_percent)
        # normalise to that range
        pca = (pca-lo)/(hi-lo)
        # and clip the outliers, which are now outside
        pca = np.clip(pca,0,1)
        # and put back into the original range
        pca = pca*(img_max-img_min)+img_min

    # reshape back to image shape and type conversion
    pca = pca.astype(np.float32)
    # paste masked area into original subimage, we do this with flattened version
    # of the images to match the flat mask we made.
    orig = orig.flatten()
    pca = pca.flatten()
    np.putmask(orig, ~mask, pca)
    return orig.reshape(orig_shape), stddevs, eigvals






@xformtype
class XFormPCA(XFormType):
    """
    Perform a principal component analysis and optionally a whitening transform or decorrelation
    stretch.

    **Ignores DQ and uncertainty**

    ## Standard recipe for **decorrelation stretch**:

    * Mode = decorrelation stretch
    * Stretch/whitening = stretch
    * Clip outliers to around 2%
    * Set both RGB normalisation and histogram equalisation

    See below for what this actually does!

    ## Details

    This node first performs a Principle Component Analysis (PCA) on all bands of an image.
    The output image consists of the principal components, with the most significant first.
    The RGB output - also shown in the canvas - is selected from these bands by the Component RGB Mapping,
    and some further processing can take place on this (see below).

    On the PCA image we optionally perform a whitening transform or a stretch.

    * A **whitening transform** will divide each PC by its standard deviation (so that the
      resulting data has an identity covariance matrix).
    * A **stretch** will apply a stretch factor to the PCs, (mean of eigenvalues / eigenvalue)

    We then either leave the result in the PCA space, so that channel 0 holds the component
    with the most variation, channel 1 holds the next most varying component etc., or we
    transform the image back into the original colour space, so the node performs a **decorrelation
    stretch**.

    Then a contrast stretch is done in which all outliers above and below a certain percentile
    of the entire image are set to 0 or 1, and remaining values are stretched to fill the gaps.

    The resulting image is sent to the PCA output before further processing.

    The remaining steps only take place on the RGB representation of the image, whose bands
    are selected by the "Component RGB mapping" boxes.

    * **Normalize RGB** will normalise the RGB bands **separately** to the [0,1] range. This
      is usually required because the PCA image bands have very different amplitudes.
    * **Histogram equalisation** can be applied to the RGB image. This
      redistributes the intensity values of an image so that they occupy the available dynamic
      range more evenly. It works by computing the image’s histogram,
      converting it into a cumulative distribution function (CDF), and then remapping each pixe
      according to this CDF.

    The standard deviations of the original input image and the eigenvalues (i.e. magnitudes)
    of the principal components are also shown and output.
    """

    OUT_RGB = 0
    OUT_PCA = 1
    OUT_EIGS = 2
    OUT_SDS = 3

    def __init__(self):
        super().__init__("PCA", "processing", "0.0.0", hasEnable=False)
        self.addInputConnector("", Datum.IMG, "input image")
        self.addOutputConnector("rgb", Datum.IMG, "RGB image selected by component mapping")
        self.addOutputConnector("PCA", Datum.IMG, "PCA image")
        self.addOutputConnector("eigs", Datum.NUMBER, "eigenvalues of principal components")
        self.addOutputConnector("sds", Datum.NUMBER, "standard deviations of original image bands")
        self.params = TaggedDictType(
            rgbmapping = ("rgb mapping", TaggedListType(int,[0,1,2], 0)),
            mode = ("PCA or decorr stretch mode", str, "pca", ["pca","decorr"] ),
            stretch = ("Stretch/decorr mode", str, "none", ["none","whiten","stretch"]),
            clip=("percentile outliers to clip in postprocessing", float, 5.0),
            normalize=("normalise RGB output", bool, True),
            histequal=("apply histogram equalization to RGB output", bool, False),
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
            band_count = node.inimg.channels
            newimg, stddevs, eigvals = process(subimage,
                                               mode=node.params.mode,
                                               stretch=node.params.stretch,
                                               clip_percent=node.params.clip)

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

            ##### Now construct the RGB output ############

            # Step one is getting the rgb-mapped input image
            img = node.inimg.rgbImage()
            # construct a subimage to modify
            subimage = img.subimage()
            # then extract the bands we want from the PCA output
            bands = node.params.rgbmapping.get()
            # making sure they're in range
            if any([x>=band_count for x in bands]):
                ui.log(f"Some bands are out of range: {bands}")
            bands = [min(x,band_count-1) for x in bands]
            newimg = newimg[:,:,bands]

            # construct sources and fixup the DQ bits to show there is no uncertainty
            sources = MultiBandSource([sources]*3)
            dq = image.imgmerge([dqval]*3)
            dq |= pcot.dq.NOUNCERTAINTY

            # normalize and histequal if required
            if node.params.normalize:
                from pcot.operations.norm import _norm
                bands = image.imgsplit(newimg)
                bands = [_norm(x)[0] for x in bands]
                newimg = image.imgmerge(bands)
            if node.params.histequal:
                from pcot.xforms.xformhistequal import equalize
                newimg = equalize(newimg, subimage.mask)

            # and paste it into the masked area in the RGB image
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
        self.w.red.currentIndexChanged.connect(lambda v: self.mappingChanged(0,v))
        self.w.green.currentIndexChanged.connect(lambda v: self.mappingChanged(1,v))
        self.w.blue.currentIndexChanged.connect(lambda v: self.mappingChanged(2,v))

        # only need to connect one of the two buttons, since changing one will change the other.
        self.w.radioDecorr.toggled.connect(self.modeChanged)
        # self.w.radioPCA.toggled.connect(self.modeChanged)

        self.w.stretch.currentTextChanged.connect(self.stretchChanged)

        self.w.clip.valueChanged.connect(self.clipChanged)
        self.w.norm.toggled.connect(self.normChanged)
        self.w.histequal.toggled.connect(self.histEqualChanged)
        self.w.canvas.nodeToRerunIfMappingChanged = n
        self.onNodeChanged()

    def modeChanged(self,_):
        self.mark()
        if self.w.radioDecorr.isChecked():
            self.node.params.mode = "decorr"
        else:
            self.node.params.mode = "pca"
        self.changed()

    def stretchChanged(self,t):
        t = t.split()[0]
        self.mark()
        self.node.params.stretch = t
        self.changed()

    def histEqualChanged(self, state):
        self.mark()
        self.node.params.histequal = state
        self.changed()

    def normChanged(self, state):
        self.mark()
        self.node.params.normalize = state
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
        if params.mode == "decorr":
            self.w.radioDecorr.setChecked(True)
        else:
            self.w.radioPCA.setChecked(True)

        idx = self.w.stretch.findText(params.stretch, QtCore.Qt.MatchFlag.MatchStartsWith)
        self.w.stretch.setCurrentIndex(idx)

        self.w.norm.setChecked(params.normalize)
        self.w.histequal.setChecked(params.histequal)
        self.w.clip.setValue(params.clip)


        # hackery here to get the constant because of the xformtype wrapper
        self.w.canvas.display(self.node.getOutput(XFormPCA._cls.OUT_RGB))

        # output
        sf = pcot.config.data.sigfigs
        if self.node.stddevs is None:
            self.w.stdDevsText.setText("No data")
            self.w.eigenValsText.setText("No data")
        else:
            s = [f"{i}: {round(self.node.stddevs[i],sf)}" for i in range(len(self.node.stddevs))]
            self.w.stdDevsText.setText("\n".join(s))
            s = [f"{i}: {round(self.node.eigenvals[i],sf)}" for i in range(len(self.node.stddevs))]
            self.w.eigenValsText.setText("\n".join(s))

