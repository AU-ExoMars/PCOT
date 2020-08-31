from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import Qt
import sys

import ui.tabs
import xform
import graphview,palette,graphscene

# import all transform types (see the __init__.py there)
from xforms import *

class MainUI(ui.tabs.DockableTabWindow):
    def autoLayout(self):
        self.scene = graphscene.XFormGraphScene(self)
        
    def saveAction(self):
        self.graph.serialise()
        pass
    def loadAction(self):
        pass
        
    def __init__(self):
        super().__init__()
        uic.loadUi('assets/main.ui',self)
        self.initTabs()
        
        print(self.actionSave)

        # connect buttons etc.        
        self.autolayoutButton.clicked.connect(self.autoLayout)
        self.dumpButton.clicked.connect(lambda: self.graph.dump())
        self.actionSave.triggered.connect(self.saveAction)
        self.actionLoad.triggered.connect(self.loadAction)
        
        # set up the scrolling palette and make the buttons therein
        palette.setup(self.paletteArea,self.paletteContents,self.view)

        
        # create a dummy graph with just a source
        self.graph=xform.XFormGraph()
        source = self.graph.create("source")
        

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

