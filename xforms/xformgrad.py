from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas,ui.mplwidget
from xform import xformtype,XFormType
from pancamimage import Image

def applyGradient(img,mask,grad):
    masked = np.ma.masked_array(img,mask=~mask)
    # construct 3 channel copy of image to write into
    cp = cv.merge((img,img,img))
    # turn gradient into lookup tables for each channel
    xs=np.array([x for x,(r,g,b) in grad])
    rs=np.array([r for x,(r,g,b) in grad])
    gs=np.array([g for x,(r,g,b) in grad])
    bs=np.array([b for x,(r,g,b) in grad])
    # build the r,g,b channels with interpolation into the lookup
    rs = np.interp(masked,xs,rs)
    gs = np.interp(masked,xs,gs)
    bs = np.interp(masked,xs,bs)
    # and stack them into a single image. To do this, though, we
    # need the full 3 channel mask.
    print(mask.shape)
    h,w = mask.shape
    # flatten and repeat each element thrice
    mask3 = np.repeat(np.ravel(mask),3) 
    # put into a h,w,3 array            
    mask3 =  np.reshape(mask3,(h,w,3))
    # write to the 3 channel copy using that mask
    np.putmask(cp,mask3,cv.merge((rs,gs,bs)).astype(np.float32))
    return cp
        

presetGradients = {
    "topo": [
            (0.000000, (0.298039,0.000000,1.000000)),
            (0.111111, (0.000000,0.098039,1.000000)),
            (0.222222, (0.000000,0.501961,1.000000)),
            (0.333333, (0.000000,0.898039,1.000000)),
            (0.444444, (0.000000,1.000000,0.301961)),
            (0.555556, (0.301961,1.000000,0.000000)),
            (0.666667, (0.901961,1.000000,0.000000)),
            (0.777778, (1.000000,1.000000,0.000000)),
            (0.888889, (1.000000,0.870588,0.349020)),
            (1.000000, (1.000000,0.878431,0.701961)),
        ],
        
    "grey": [
        (0, (0,0,0)),
        (1, (1,1,1)),
        ],
}            
        

@xformtype
class XformGradient(XFormType):
    """Convert a greyscale image to a colour gradient image for better visibility"""
    
    def __init__(self):
        super().__init__("gradient","data","0.0.0")
        self.addInputConnector("","imggrey")
        self.addOutputConnector("","imgrgb")
        self.autoserialise=('gradient',)
        self.hasEnable=True

    def createTab(self,n,w):
        return TabGradient(n,w)
        
    def init(self,node):
        node.gradient = presetGradients['topo']
        
    def perform(self,node):
        img = node.getInput(0)
        if img is None:
            node.img = None
        elif node.enabled:
            if img.channels == 1:
                subimage = img.subimage()
                newsubimg = applyGradient(subimage.img,subimage.fullmask(),node.gradient)
                outimg = Image(img.rgb(),img.sources)
                node.img = outimg.modifyWithSub(subimage,newsubimg)
                print(node.img)
            else:
                node.img = None
        else:
            node.img = img
        node.setOutput(0,node.img)
        
        

class TabGradient(ui.tabs.Tab):
    def __init__(self,node,w):
        super().__init__(w,node,'assets/tabgrad.ui')
        self.w.gradient.gradientChanged.connect(self.gradientChanged)
        self.w.presetCombo.currentIndexChanged.connect(self.loadPreset)
        for n in presetGradients:
            self.w.presetCombo.insertItem(1000,n)
        self.onNodeChanged()
        
    def loadPreset(self):
        name = self.w.presetCombo.currentText()
        print(name)
        if name in presetGradients:
            self.w.gradient.setGradient(presetGradients[name])
            self.w.gradient.update()
            self.node.gradient = self.w.gradient.gradient()
            self.perform()
        
            
    def onNodeChanged(self):
        self.w.gradient.setGradient(self.node.gradient)
        self.w.canvas.display(self.node.img)

    def gradientChanged(self):
        self.node.gradient = self.w.gradient.gradient()
        self.perform()
