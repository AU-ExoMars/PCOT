import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from xforms.tabimage import TabImage

# this transform takes an image and places it at a position inside another image.
# The inset position is taken either from a control, or if this isn't present,
# from a rubberband selection as in xformcrop.

@xformtype
class XformInset(XFormType):
    def __init__(self):
        super().__init__("inset","0.0.0")
        self.addInputConnector("img","img")
        self.addInputConnector("inset","img")
        self.addInputConnector("rect","rect")
        self.addOutputConnector("","img")
        self.autoserialise=('insetrect',)

    def createTab(self,n):
        return TabInset(n)
        
    def generateOutputTypes(self,node):
        node.matchOutputsToInputs([(0,0)])

    def init(self,node):
        node.img = None
        node.insetrect = None
        
    def perform(self,node):
        image = node.getInput(0)
        inset = node.getInput(1)
        inrect = node.getInput(2)
        
        # if there is no input rect we use the rubberbanded one set by the tab
        if inrect is None:
            inrect = node.insetrect
        
        ui.mainui.log("Inrect {}, rubber: {}".format(inrect,node.insetrect))
        if inrect is None:
            out = image # neither rects are set, just dupe the input
        else:
            x,y,w,h = inrect # get the rectangle
            out = image.copy()
            if inset is None:
                # there's no inset image, draw a rectangle
                cv.rectangle(out,(x,y),(x+w,y+h),(0,0,255),-1) # -1=filled
            else:
                # resize the inset
                t = cv.resize(inset,dsize=(w,h),interpolation=cv.INTER_CUBIC)
                out[y:y+h,x:x+w]=t

        node.img = out
        node.setOutput(0,out)
        

class TabInset(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabimage.ui')
        # set the paint hook in the canvas so we can draw on the image
        self.w.canvas.paintHook=self
        self.w.canvas.mouseHook=self
        # sync tab with node
        self.onNodeChanged()
        self.mouseDown=False

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        # we just draw the composited image
        if self.node.img is not None:
            self.w.canvas.display(self.node.img)

    # extra drawing!
    def canvasPaintHook(self,p):
        # we could draw the rectangle in here (dividing all sizes down by the canvas scale)
        # but it's more accurate done as above in onNodeChanged
        pass
            
    def canvasMouseMoveEvent(self,x2,y2,e):
        if self.mouseDown:
            p=e.pos()
            x,y,w,h = self.node.insetrect
            w = x2-x
            h = y2-y
            if w<10:
                w=10
            if h<10:
                h=10
            self.node.insetrect=(x,y,w,h)
            self.node.perform()
        self.w.canvas.update()
        
    def canvasMousePressEvent(self,x,y,e):
        p = e.pos()
        w = 10 # min crop size
        h = 10
        self.mouseDown=True
        self.node.insetrect=(x,y,w,h)
        self.node.perform()
        self.w.canvas.update()

    def canvasMouseReleaseEvent(self,x,y,e):
        self.mouseDown=False

    
