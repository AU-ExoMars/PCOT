from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QTreeView,QFileSystemModel
from PyQt5.QtCore import Qt,QDir

import cv2 as cv
import numpy as np

import tabs,canvas
import xformgraph.xform
from xformgraph.xform import singleton,XFormType

class TabSource(tabs.Tab):
    def __init__(self,mainui,node):
        super().__init__(mainui,node,'tabsource.ui')
        # set up the file tree
        self.dirModel = QFileSystemModel()
        self.dirModel.setRootPath(QDir.currentPath())
        self.dirModel.setNameFilters(["*.jpg","*.png"])
        tree = self.getUI(QtWidgets.QTreeView,'treeView')
        tree.setModel(self.dirModel)
        tree.setRootIndex(self.dirModel.index(QDir.currentPath()))
        tree.setIndentation(10)
        tree.setSortingEnabled(True)
        tree.setColumnWidth(0, tree.width() / 1.5)
        tree.setColumnHidden(1,True)
        tree.setColumnHidden(2,True)
        tree.doubleClicked.connect(self.fileClickedAction)
        self.treeView=tree
        self.canvas = self.getUI(canvas.Canvas,'canvas')
        # sync tab with node
        self.onNodeChanged()

    # causes the tab to update itself from the node
    def onNodeChanged(self):
        self.canvas.display(self.node.outputs[0])
        
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

    # the "perform" of a source is just to output its data
    def perform(self,node):
        node.setOutput(0,node.img)
    
