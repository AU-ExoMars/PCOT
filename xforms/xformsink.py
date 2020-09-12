import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage
from pancamimage import Image

# The node type itself, a subclass of XFormType with the @xformtype decorator which will
# calculate a checksum of this source file and automatically create the only instance which
# can exist of this class (it's a singleton).

@xformtype
class XformSink(XFormType):
    def __init__(self):
        # call superconstructor with the type name and version code
        super().__init__("sink","0.0.0")
        # set up a single input which takes an image of any type. The connector could have
        # a name in more complex node types, but here we just have an empty string.
        self.addInputConnector("","img")

    # this creates a tab when we want to control or view a node of this type. This uses
    # the built-in TabImage, which contains an OpenCV image viewer.
    def createTab(self,n):
        return TabImage(n)

    # actually perform a node's action, which happens when any of the nodes "upstream" are changed
    # and on loading.
    def perform(self,node):
        # get the input (index 0, our first and only input). That's all - we just store a reference
        # to the image in the node. The TabImage knows how to display nodes with "img" attributes,
        # and does the rest.
        node.img = node.getInput(0)
    def init(self,node):
        # initialise the node by setting its img to None.
        node.img = None


