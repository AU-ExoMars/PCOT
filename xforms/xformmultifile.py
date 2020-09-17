from os import listdir
import re
from os.path import isfile,join
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt,QDir

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from pancamimage import Image
["*.jpg","*.png","*.ppm","*.tga","*.tif"]
IMAGETYPERE = re.compile(r".*\.(?i:jpg|png|ppm|tga|tif)")

@xformtype
class XFormMultiFile(XFormType):
    """Load multiple image files into greyscale channels"""
    def __init__(self):
        super().__init__("multifile","0.0.0")
        self.autoserialise=(('filters','dir','files'))
        
    def createTab(self,n):
        return TabMultiFile(n)
        
    def init(self,node):
        node.filters=[]
        node.dir='.'
        node.files=[]
        
    def perform(self,node):
        pass

class TabMultiFile(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabmultifile.ui')

        self.w.getinitial.clicked.connect(self.getInitial)
        self.w.filters.textChanged.connect(self.filtersChanged)
        self.allFiles=[]
        self.onNodeChanged()
        
    def getInitial(self):
        res = QtWidgets.QFileDialog.getExistingDirectory(ui.mainui,'Directory for images','.')
        if res!='':
            self.selectDir(res)

    def filtersChanged(self,t):
        self.node.filters=t.split(",")
        self.buildModel()

    def onNodeChanged(self):
        self.w.filters.setText(",".join(self.node.filters))
        self.selectDir(self.node.dir)
                    
    def buildModel(self):
        self.model = QtGui.QStandardItemModel(self.w.filelist)
        for x in self.allFiles:
           add=True
           for f in self.node.filters:
               if not f in x:
                   add=False
                   break
           if add:
               item = QtGui.QStandardItem(x)
               item.setCheckable(True)
               if x in self.node.files:
                   item.setCheckState(Qt.Checked)
               self.model.appendRow(item)
        self.w.filelist.setModel(self.model)
        self.model.dataChanged.connect(self.checkedChanged)
        
    def checkedChanged(self):
        self.node.files=[]
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.checkState()==Qt.Checked:
                self.node.files.append(item.text())
        
    def selectDir(self,dir):
        if self.node.dir != dir:
            self.node.files=[]
        self.w.dir.setText(dir)
        # get all the files in dir which are images 
        self.allFiles = [f for f in listdir(dir) if isfile(join(dir, f))
            and IMAGETYPERE.match(f) is not None]
        self.node.dir = dir
        self.buildModel()
            
         
