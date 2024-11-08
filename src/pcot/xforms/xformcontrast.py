import numpy as np

from pcot import dq
from pcot.datum import Datum
import pcot.ui.tabs
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.utils import image, SignalBlocker
from pcot.xform import xformtype, XFormType


# performs contrast stretching on a single channel. The image is a (h,w) numpy array.
# There is also a (h,w) array mask. We also set DQ saturation bits in the DQ array passed in.

def contrast1(img, tol, mask, dqToSet):
    # get the masked data to calculate the percentiles
    # need to compress it, because percentile ignores masks. 
    # Note the negation of the mask; numpy is weird- True means masked.
    B = img.copy()
    masked = np.ma.masked_array(data=B, mask=~mask)
    comp = masked.compressed()

    # find lower and upper limit for contrast stretching, and set those in the
    # masked image
    tol = 100 * tol   # convert to percent
    low, high = np.percentile(comp, tol), np.percentile(comp, 100 - tol)

    satlow = masked < low
    sathigh = masked > high

    masked[satlow] = low
    masked[sathigh] = high

    dqToSet[satlow] |= dq.SAT
    dqToSet[sathigh] |= dq.SAT

    # ...rescale the color values in the masked image to 0..1
    masked = (masked - masked.min()) / (masked.max() - masked.min())

    # that has actually written ALL the entries, not just the mask. Drop the
    # masked entries back into the original array.
    np.putmask(B, mask, masked)
    return B


# The node type itself, a subclass of XFormType with the @xformtype decorator which will
# calculate a checksum of this source file and automatically create the only instance which
# can exist of this class (it's a singleton).

@xformtype
class XformContrast(XFormType):
    """
    Perform a simple contrast stretch separately on each channel. The stretch is linear around the midpoint
    and excessive values are clamped. The knob controls the amount of stretch applied. Uncertainty is discarded."""

    # type constructor run once at startup
    def __init__(self):
        # call superconstructor with the type name and version code
        super().__init__("contrast stretch", "processing", "0.0.0")
        # set up a single input which takes an image of any type. The connector could have
        # a name in more complex node types, but here we just have an empty string.
        self.addInputConnector("", Datum.IMG)
        # and a single output which produces an image of any type
        self.addOutputConnector("", Datum.IMG)
        # There is one data item which should be saved - the "tol" (tolerance) control value.
        # A TaggedDict in the node, also called "params," will be created from this template.
        self.params = TaggedDictType(
            tol=("Contrast stretch tolerance (between 0 and 0.5 exclusive)", float, 0.2)
        )

    # this creates a tab when we want to control a node. See below for the class definition.
    def createTab(self, n, w):
        return TabContrast(n, w)

    # set up each individual node when it is created: We don't need to do anything here because
    # the parameters will self-initialise to their default values.
    def init(self, node):
        pass

    # actually perform a node's action, which happens when any of the nodes "upstream" are changed
    # and on loading.
    def perform(self, node):
        # get the input (index 0, our first and only input)
        img = node.getInput(0, Datum.IMG)
        if img is None:
            # there is no image, so the output will be no image
            out = None
        else:
            # otherwise, it depends on the image type. If it has three dimensions it must
            # be RGB, so generate the node's image using contrast(), otherwise it must be
            # single channel, so use contrast1(). First, though, we need to extract the subimage
            # selected by the ROI (if any)
            subimage = img.subimage()
            dqv = subimage.maskedDQ().copy()
            tol = node.params.tol
            if img.channels == 1:
                # note use of the "params" TaggedDict here, with tol in it. This is the TaggedDict
                # created from the "params" TaggedDictType in the type singleton.
                newsubimg = contrast1(subimage.img, tol, subimage.mask, dqv)
            else:
                imgs = image.imgsplit(subimage.img)
                dqs = image.imgsplit(dqv)
                newsubimg = image.imgmerge([contrast1(x, tol, subimage.mask, y) for x, y in zip(imgs, dqs)])
            # having got a modified subimage, we need to splice it in. No uncertainty is passed in, so the
            # uncertainty is discarded and the NOUNC bit set.
            out = img.modifyWithSub(subimage, newsubimg, dqv=dqv)
            # set the RGB mapping for this image to be the one stored in the node
            out.setMapping(node.mapping)
            # and wrap in a Datum
            out = Datum(Datum.IMG, out)
        # now do the output
        node.setOutput(0, out)


# This is the user interface for the node type, which is created when we double click on a node.
# It's a subclass of ui.tabs.Tab: a dockable tab.
class TabContrast(pcot.ui.tabs.Tab):
    # constructor
    def __init__(self, node, w):
        # create the tab, setting the main UI window as the parent and loading
        # the user interface from the given .ui file generated by Qt Designer.
        super().__init__(w, node, 'tabcontrast.ui')
        # connect the spinbox control with the setContrast method - when the spinbox changes,
        # that method will be called with the new value. Note that the box is actually loaded
        # into a subwidget called "w".
        self.w.spinBox.valueChanged.connect(self.setContrast)

        # we set this in setContrast so that calling changed(), which calls onNodeChanged(),
        # doesn't change the widget - because setContrast is called in response to a widget
        # change. Remove the check in onNodeChanged and type values into the box
        # to see what happens if we don't have this.
        self.inSetContrast = False

        # We call onNodeChanged to set the tab with the initial values from the node.
        self.nodeChanged()

    # The value of the widget has changed. We set the tolerance and then call perform().
    def setContrast(self, v):
        self.mark()
        self.inSetContrast = True
        self.node.params.tol = v
        self.changed()
        self.inSetContrast = False

    # This is called from the tab constructor and from the loading system: it updates the
    # tab's controls with the values in the node. In this case, it also displays the stored
    # image on the tab's canvas - this is a class in the ui package which can display OpenCV
    # images.
    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)

        if not self.inSetContrast:
            # see the constructor for why the check of inSetContrast is here
            self.w.spinBox.setValue(self.node.params.tol)
        self.w.canvas.display(self.node.getOutput(0))
