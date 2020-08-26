from PyQt5 import QtWidgets, uic
import graphview
import sys
import xformgraph.xform,xformgraph.draw
from xformgraph.xform import singleton,XFormType

# dummy transform types

@singleton
class XformSource(XFormType):
    def __init__(self):
        super().__init__("source")
        self.addOutputConnector("rgb","img888")


@singleton
class XformSink(XFormType):
    def __init__(self):
        super().__init__("sink")
        self.addInputConnector("rgb","img888")
    

@singleton
class XformGrey(XFormType):
    def __init__(self):
        super().__init__("greyscale")
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("grey","imggrey")

@singleton
class XformSplit(XFormType):
    def __init__(self):
        super().__init__("split")
        self.addInputConnector("rgb","img888")
        self.addOutputConnector("r","imggrey")
        self.addOutputConnector("g","imggrey")
        self.addOutputConnector("b","imggrey")

@singleton
class XformMerge(XFormType):
    def __init__(self):
        super().__init__("merge")
        self.addInputConnector("r","imggrey")
        self.addInputConnector("g","imggrey")
        self.addInputConnector("b","imggrey")
        self.addOutputConnector("rgb","img888")

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
        self.getUI(QtWidgets.QPushButton,'dumpButton').clicked.connect(lambda: self.graph.dump())
        
        self.view = self.getUI(graphview.GraphView,'graphicsView')
        self.show()
        
        # create a dummy graph
        self.graph=xformgraph.xform.XFormGraph()
        split = self.graph.create("split")
        merge = self.graph.create("merge")
        source = self.graph.create("source")
        sink = self.graph.create("sink")
        
        split.connect(0,source,0)
        merge.connect(0,split,0)
        merge.connect(1,split,1)
        merge.connect(2,split,2)
        sink.connect(0,merge,0)
        
        # and view it - this will also link to the view, which the scene needs
        # to know about so it can modify its drag mode.
        self.scene = xformgraph.draw.XFormGraphScene(self.graph,self.view)
        

app = QtWidgets.QApplication(sys.argv) 
window = MainUI() # Create an instance of our class
app.exec_() # Start the application

