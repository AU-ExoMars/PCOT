from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from pancamimage import ImageCube

# performs contrast stretching on a single channel. The image is a (h,w) numpy array.
# There is also a (h,w) array mask.

def contrast1(img,tol,mask):
    # get the masked data to calculate the percentiles
    # need to compress it, because percentile ignores masks. 
    # Note the negation of the mask; numpy is weird- True means masked.
    B = img.copy()
    masked = np.ma.masked_array(data=B,mask=~mask)
    comp = masked.compressed()
    
    # find lower and upper limit for contrast stretching, and set those in the
    # masked image
    low, high = np.percentile(comp, 100*tol), np.percentile(comp, 100-100*tol)
    masked[masked<low] = low
    masked[masked>high] = high

    # ...rescale the color values in the masked image to 0..1
    masked = (masked - masked.min())/(masked.max() - masked.min())
    
    # that has actually written ALL the entries, not just the mask. Drop the
    # masked entries back into the original array.
    np.putmask(B,mask,masked)
    return B

# The node type itself, a subclass of XFormType with the @xformtype decorator which will
# calculate a checksum of this source file and automatically create the only instance which
# can exist of this class (it's a singleton).

@xformtype
class XformContrast(XFormType):
    """Perform a simple contrast stretch separately on each channel. The stretch is linear around the midpoint
    and excessive values are clamped. The knob controls the amount of stretch applied."""
    # type constructor run once at startup
    def __init__(self):
        # call superconstructor with the type name and version code
        super().__init__("contrast stretch","processing","0.0.0")
        # set up a single input which takes an image of any type. The connector could have
        # a name in more complex node types, but here we just have an empty string.
        self.addInputConnector("","img")
        # and a single output which produces an image of any type (but this will be modified
        # when the input is wired up to specify the exact image type - done in
        # generateOutputTypes). 
        self.addOutputConnector("","img")
        # There is one data item which should be saved - the "tol" (tolerance) control value.
        self.autoserialise=('tol',)
        self.hasEnable=True
        
    # this creates a tab when we want to control a node. See below for the class definition.
    def createTab(self,n,w):
        return TabContrast(n,w)
        
    # When we connect an input, we want the output type to be changed to match it - currently
    # the output is just "some kind of image". This will do this by making output 0 match the
    # type of input 0.
    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0)])

    # set up each individual node when it is created: there will be no image (since we haven't
    # read the input yet) and the default tolerance is 0.2. Note this sets values in the node,
    # not in "self" which is the type singleton.
    def init(self,node):
        node.img = None
        node.tol = 0.2
        
    # actually perform a node's action, which happens when any of the nodes "upstream" are changed
    # and on loading.
    def perform(self,node):
        # get the input (index 0, our first and only input)
        img = node.getInput(0)
        if img is None:
            # there is no image, so the stored image (and output) will be no image
            node.img = None
        elif not node.enabled:
            node.img = img
        else:
            # otherwise, it depends on the image type. If it has three dimensions it must
            # be RGB, so generate the node's image using contrast(), otherwise it must be
            # single channel, so use contrast1(). First, though, we need to extract the subimage
            # selected by the ROI (if any)
            subimage = img.subimage()
            if img.channels==1:
                newsubimg = contrast1(subimage.img,node.tol,subimage.mask)
            else:
                newsubimg = cv.merge([contrast1(x,node.tol,subimage.mask) for x in cv.split(subimage.img)])
            # having got a modified subimage, we need to splice it in
            node.img = img.modifyWithSub(subimage,newsubimg)
        # Now we have generated the internally stored image, output it to output 0. This will
        # cause all nodes "downstream" to perform their actions.
        node.setOutput(0,node.img)



# This is the user interface for the node type, which is created when we double click on a node.
# It's a subclass of ui.tabs.Tab: a dockable tab.
class TabContrast(ui.tabs.Tab):
    # constructor
    def __init__(self,node,w):
        # create the tab, setting the main UI window as the parent and loading
        # the user interface from the given .ui file generated by Qt Designer.
        super().__init__(w,node,'assets/tabcontrast.ui')
        # connect the "dial" control with the setContrast method - when the dial changes,
        # that method will be called with the new value. Note that the dial is actually loaded
        # into a subwidget called "w".
        self.w.dial.valueChanged.connect(self.setContrast)

        # We call onNodeChanged to set the tab with the initial values from the node.
        self.onNodeChanged()

    # The value of the dial has changed. It ranges from 0-100, so we set the 
    # tolerance by scaling the value down. We then call perform().
    def setContrast(self,v):
        self.node.tol = v/200
        self.changed()

    # This is called from the tab constructor and from the loading system: it updates the
    # tab's controls with the values in the node. In this case, it also displays the stored
    # image on the tab's canvas - this is a class in the ui package which can display OpenCV
    # images.
    def onNodeChanged(self):
        self.w.dial.setValue(self.node.tol*200)        
        self.w.canvas.display(self.node.img)

