from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import Qt
import sys,traceback

import ui.tabs
import xform
import graphview,palette,graphscene

# import all transform types (see the __init__.py there)
from xforms import *

class MainUI(ui.tabs.DockableTabWindow):
    def autoLayout(self):
        # called autoLayout, because that's essentially the end-user
        # visible action. Will delete the old scene and create a new scene,
        # linking the viewer to it.
        self.scene = graphscene.XFormGraphScene(self,True)
        
    def save(self,fname):
        try:
            with open(fname,'w') as f:
                self.graph.serialise(f)
                self.msg("File saved")
        except Exception as e:
            traceback.print_exc()
            self.msg("cannot save file {}: {}".format(fname,e))
    
    def load(self,fname):
        try:
            with open(fname) as f:
                self.graph.deserialise(f)
                # now we need to "autolayout" but preserve the xy data
                self.scene = graphscene.XFormGraphScene(self,False)
                self.msg("File loaded")
                self.saveFileName = fname
        except Exception as e:
            traceback.print_exc()
            self.msg("cannot open file {}: {}".format(fname,e))
        
    def saveAsAction(self):
        res = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', '.',"JSON files (*.json)")
        if res[0]!='':
            self.save(res[0])
            self.saveFileName = res[0]
            
    def saveAction(self):
        if self.saveFileName is None:
            self.saveAsAction()
        else:
            self.save(self.saveFileName)
                
    def openAction(self):
        res = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', '.',"JSON files (*.json)")
        if res[0]!='':
            self.closeAllTabs()
            self.load(res[0])
            
    def newAction(self):
        # create a dummy graph with just a source
        self.graph=xform.XFormGraph()
        source = self.graph.create("source")
        self.saveFileName = None
        # set up its scene and view
        self.autoLayout() # builds the scene
        

    def msg(self,t): # show msg on status bar
        self.statusBar.showMessage(t)
        
    def log(self,s):
        self.logText.append(s)
        
    def logXFormException(self,node,e):
        self.msg("Exception in {}: {}".format(node.name,e))
        self.log('<font color="red">Exception in <b>{}</b>: </font> {}'.format(node.name,e))
        
    def __init__(self):
        super().__init__()
        ui.mainui = self
        uic.loadUi('assets/main.ui',self)
        self.initTabs()
        self.saveFileName = None
        
        # connect buttons etc.        
        self.autolayoutButton.clicked.connect(self.autoLayout)
        self.dumpButton.clicked.connect(lambda: self.graph.dump())
        self.actionSave_As.triggered.connect(self.saveAsAction)
        self.action_New.triggered.connect(self.newAction)
        self.actionSave.triggered.connect(self.saveAction)
        self.actionOpen.triggered.connect(self.openAction)

        # get and activate the status bar        
        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)

        
        # set up the scrolling palette and make the buttons therein
        palette.setup(self.paletteArea,self.paletteContents,self.view)

        self.newAction() # create empty graph

        self.show()
        self.msg("OK")
        self.load("test.json")

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
window=MainUI() # Create an instance of our class
app.exec_() # Start the application

