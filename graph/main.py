from PyQt5 import QtWidgets, uic
import graphview
import sys
import xformgraph.xform

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
        self.addInputConnector("r","imggrey")
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
        
        self.scene = QtWidgets.QGraphicsScene()
        
        self.view = self.getUI(graphview.GraphView,'graphicsView')
        self.view.setScene(self.scene)
        self.show()
        
        self.graph=xformgraph.xform.Graph()
        x = self.graph.create("merge")
        

app = QtWidgets.QApplication(sys.argv) 
window = MainUI() # Create an instance of our class
app.exec_() # Start the application

