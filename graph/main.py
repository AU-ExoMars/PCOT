from PyQt5 import QtWidgets, uic
import graphview
import sys
import xformgraph.xform,xformgraph.draw

# dummy transform types

class XformSource(xformgraph.xform.XFormType):
    def __init__(self):
        super().__init__("source")
        self.addOutputConnector("rgb","img888")
XformSource() # force creation       

class XformSink(xformgraph.xform.XFormType):
    def __init__(self):
        super().__init__("sink")
        self.addInputConnector("rgb","img888")
XformSink() # force creation       
    

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
    def rebuild(self):
        self.scene = xformgraph.draw.XFormGraphScene(self.graph,self.view)
    def __init__(self):
        super().__init__()
        uic.loadUi('main.ui',self)
        
        self.getUI(QtWidgets.QPushButton,'rebuildButton').clicked.connect(self.rebuild)
        
        self.view = self.getUI(graphview.GraphView,'graphicsView')
        self.show()
        
        # create a dummy graph
        self.graph=xformgraph.xform.XFormGraph()
        x = self.graph.create("split")
        y = self.graph.create("merge")
        z = self.graph.create("source")
        zz = self.graph.create("sink")
        z.connectOut(0,x,0)
        x.connectOut(0,y,1)
        x.connectOut(1,y,2)
        y.connectOut(0,zz,0)
        
        # and view it - this will also link to the view, which the scene needs
        # to know about so it can modify its drag mode.
        self.scene = xformgraph.draw.XFormGraphScene(self.graph,self.view)
        

app = QtWidgets.QApplication(sys.argv) 
window = MainUI() # Create an instance of our class
app.exec_() # Start the application

