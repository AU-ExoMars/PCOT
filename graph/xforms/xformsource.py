from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QTreeView,QFileSystemModel
from PyQt5.QtCore import Qt,QDir

import cv2 as cv
import numpy as np

import ui.tabs,ui.canvas
from xform import singleton,XFormType


sn=0
def snark():
    global sn
    print(sn)
    sn+=1
    

class TabSource(ui.tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'assets/tabsource.ui')
        # set up the file tree
        self.dirModel = QFileSystemModel()
        self.dirModel.setRootPath("/")
        self.dirModel.setNameFilters(["*.jpg","*.png"])
        self.dirModel.setNameFilterDisables(False)
        print(self.__dict__)
        tree = self.w.treeView
        self.w.treeView.setModel(self.dirModel)

        idx = self.dirModel.index(QDir.currentPath())
        self.w.treeView.selectionModel().select(idx,QtCore.QItemSelectionModel.Select)
        self.w.treeView.setIndentation(10)
        self.w.treeView.setSortingEnabled(True)
        self.w.treeView.setColumnWidth(0, self.w.treeView.width() / 1.5)
        self.w.treeView.setColumnHidden(1,True)
        self.w.treeView.setColumnHidden(2,True)
        self.w.treeView.doubleClicked.connect(self.fileClickedAction)
        self.w.treeView.scrollTo(idx)
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.w.canvas.display(self.node.outputs[0])
        
    # this sets the file IN THE NODE. We store all data in the node,
    # the tab is just a view on the node.
    def fileClickedAction(self,idx):
        if not self.dirModel.isDir(idx):
            fname = self.dirModel.filePath(idx)
            img = cv.imread(fname)
            img = cv.cvtColor(img,cv.COLOR_BGR2RGB)
            if img is None:
                raise Exception('cannot read image')
            # set the node's data
            self.node.img = img
            # and tell it to perform (outputting the data)
            # This will also run onNodeChanged() in any attached tab
            self.node.perform()

@singleton
class XformSource(XFormType):
    def __init__(self):
        super().__init__("source")
        ## our connectors
        self.addOutputConnector("rgb","img888")

    def createTab(self,mainui,n):
        return TabSource(mainui,n)
        
    def init(self,node):
        node.img = None

    # the "perform" of a source is just to output its data
    def perform(self,node):
        node.setOutput(0,node.img)
    
