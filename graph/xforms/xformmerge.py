import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage

@xformtype
class XformMerge(XFormType):
    def __init__(self):
        super().__init__("merge")
        ## our connectors
        self.ver="0.0.0"
        self.addInputConnector("r","imggrey")
        self.addInputConnector("g","imggrey")
        self.addInputConnector("b","imggrey")
        self.addOutputConnector("rgb","img888")
        
    def createTab(self,n):
        return TabImage(n)

    def init(self,node):
        node.img = None

    def perform(self,node):
        r = node.getInput(0)
        g = node.getInput(1)
        b = node.getInput(2)
        node.img = None # preset the internal value
        
        # get shapes            
        rs = None if r is None else r.shape
        gs = None if g is None else g.shape
        bs = None if b is None else b.shape
        

        # get the shape of one of them
        s = None
        if rs is not None:
            s=rs
        elif gs is not None:
            s=gs
        elif bs is not None:
            s=bs
            
        # make sure is at least one of them present
        if s is None:
            node.setOutput(0,None)
            return
            
        # all that are present are the same size
        if (rs is not None and rs!=s) or (gs is not None and gs!=s) or (bs is not None and bs!=s):
            node.setOutput(0,None)
            return
            
        # make a black
        black = np.zeros(s,np.ubyte)
        if b is None:
            b = black
        if g is None:
            g = black
        if r is None:
            r = black
        node.img = cv.merge([r,g,b])
        node.setOutput(0,node.img)
            
