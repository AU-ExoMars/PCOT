from PyQt5 import QtWidgets, uic
import graphview
import sys
import xformgraph.xform,xformgraph.draw

# dummy transform types

class XformGrey(xformgraph.xform.XFormType):
    def __init__(self):
        super().__init__("greyscale")
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("grey","imggrey")
XformGrey() # force creation       

class XformSplit(xformgraph.xform.XFormType):
    def __init__(self):
        super().__init__("split")
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("r","imggrey")
        self.addOutputConnector("g","imggrey")
        self.addOutputConnector("b","imggrey")
XformSplit()

class XformMerge(xformgraph.xform.XFormType):
    def __init__(self):
        super().__init__("merge")
        self.addInputConnector("r","img888")
        self.addInputConnector("g","imggrey")
        self.addInputConnector("b","imggrey")
        self.addOutputConnector("rgb","img888")
XformMerge()

class MainUI(QtWidgets.QMainWindow):
    def getUI(self,type,name):
        x = self.findChild(type,name)
        if x is None:
            raise Exception('cannot find widget'+name)
        return x
    def __init__(self):
        super().__init__()
        uic.loadUi('main.ui',self)
        
        self.view = self.getUI(graphview.GraphView,'graphicsView')
        self.show()
        
        # create a dummy graph
        self.graph=xformgraph.xform.XFormGraph()
        y = self.graph.create("split")
        x = self.graph.create("merge")
        x.connectIn(0,y,0) # connect input 0 of merge to output 0 of split
        x.connectIn(1,y,1) # connect input 1 of merge to output 1 of split
        x.connectIn(2,y,2) # connect input 2 of merge to output 2 of split

        # and view it - this will also link to the view, which the scene needs
        # to know about so it can modify its drag mode.
        self.scene = xformgraph.draw.XFormGraphScene(self.graph,self.view)
        

app = QtWidgets.QApplication(sys.argv) 
window = MainUI() # Create an instance of our class
app.exec_() # Start the application

