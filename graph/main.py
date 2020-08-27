from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import Qt
import sys

import ui.tabs
import xform
import graphview,palette,graphscene

# import all transform types (see the __init__.py there)
from xforms import *

class MainUI(ui.tabs.DockableTabWindow):
    def getUI(self,type,name):
        x = self.findChild(type,name)
        if x is None:
            raise Exception('cannot find widget "'+name+'"')
        return x
    def autoLayout(self):
        self.scene = graphscene.XFormGraphScene(self)
    def __init__(self):
        super().__init__()
        uic.loadUi('assets/main.ui',self)
        self.initTabs()

        # connect buttons etc.        
        self.getUI(QtWidgets.QPushButton,'autolayoutButton').clicked.connect(self.autoLayout)
        self.getUI(QtWidgets.QPushButton,'dumpButton').clicked.connect(lambda: self.graph.dump())
        # get a handle on various things
        self.view = self.getUI(graphview.GraphView,'graphicsView')
        
        # set up the scrolling palette and make the buttons therein
        scrollArea = self.getUI(QtWidgets.QScrollArea,'palette')
        scrollAreaContent = self.getUI(QtWidgets.QWidget,'paletteContents')
        palette.setup(scrollArea,scrollAreaContent,self.view)

        
        # create a dummy graph
        self.graph=xform.XFormGraph()
#        source = self.graph.create("source")
#        sink = self.graph.create("sink")
#        sink.connect(0,source,0)

        source = self.graph.create("source")
        curve = self.graph.create("curveRGB")
        curve.connect(0,source,0)
        
        # and view it - this will also link to the view, which the scene needs
        # to know about so it can modify its drag mode.
        self.autoLayout() # builds the scene
        self.show()

    # this gets called from way down in the scene to open tabs for nodes
    def openTab(self,node):
        # has the node got a tab open already?
        if node.tab is None:
            # nope, ask the node type to make one
            node.tab = node.type.createTab(self,node)
            node.tab.node = node
        # pull that tab to the front
        self.tabWidget.setCurrentWidget(node.tab)
    
    # tab changed (this is connected up in the superclass)
    def currentChanged(self,index): # index is ignored
        if self.tabWidget.currentWidget() is None:
            # we've expanded or closed all widgets
            w = None
        else:
            w = self.tabWidget.currentWidget().node
        self.scene.currentChanged(w)
            
        
        

app = QtWidgets.QApplication(sys.argv) 
window = MainUI() # Create an instance of our class
app.exec_() # Start the application

