import re,os
from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt,QDir

import cv2 as cv
import numpy as np

import ui,ui.tabs,ui.canvas
from xform import xformtype,XFormType
from pancamimage import Image

NUMOUTS=6

IMAGETYPERE = re.compile(r".*\.(?i:jpg|png|ppm|tga|tif)")

@xformtype
class XFormMultiFile(XFormType):
    """Load multiple image files into greyscale channels"""
    def __init__(self):
        super().__init__("multifile","source","0.0.0")
        self.autoserialise=(('namefilters','dir','files','mult','filterpat'))
        for x in range(NUMOUTS):
            self.addOutputConnector("","imggrey")
        
    def createTab(self,n):
        return TabMultiFile(n)
        
    def init(self,node):
        # list of filter strings - strings which must be in any filenames
        node.namefilters=[] 
        # directory we're looking at
        node.dir='.'
        # files we have checked in the file list
        node.files=[]
        # all data in all channels is multiplied by this (used for, say, 10 bit images)
        node.mult=1
        node.filterpat=r'.*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*'
        node.filterre = None
        self.clearImages(node)
        
    def clearImages(self,node): # clear stored images
        node.imgs = [None for i in range(NUMOUTS)] # slots for enough images
        node.imgpaths = [None for i in range(NUMOUTS)] # slots for names (see perform)
        node.filters = [None for i in range(NUMOUTS)] # filter names

    @staticmethod
    def getFilterName(node,path):
        if node.filterre is None:
            return None
        else:
            m = node.filterre.match(path).groupdict()
            lens = m['lens'] if 'lens' in m else ''
            n = m['n'] if 'n' in m else ''
            return lens+n
            
    def perform(self,node):
        # compile the regexp that gets the filter ID out.
        try:
            node.filterre = re.compile(node.filterpat)
        except re.error:
            node.filterre = None

        # perform takes the first N images checked in the file list and outputs them,
        # N is the number of outputs!
        for i in range(len(node.outputs)):
            if i<len(node.files):
                imgname = node.files[i]
                # we use the relative path here, it's more right that using the absolute path
                # most of the time.
                path = os.path.relpath(os.path.join(node.dir,node.files[i]))
                if node.files[i] is not None and node.imgpaths[i]!=path:
                    # build source tuple : filename and filter name
                    source = (path,self.getFilterName(node,path),)
                    img = Image.load(path,source)
                    if img.channels!=1:
                        c = cv.split(img.img)
                        img = Image(c[0],{source})
                    node.imgs[i]=img
                    node.imgpaths[i]=path
                    print(node.filters[i])
            else:
                node.imgs[i]=None
                node.imgpaths[i]=None
                node.imgs[i]=None
            # slightly messy, post-multiplying the image like this
            # rather than on load, but multiplying on load would mean
            # reloading when the multiplier changed.
            img = None if node.imgs[i] is None else Image(node.imgs[i].img*node.mult,node.imgs[i].sources)
            node.setOutput(i,img)
            
        

class TabMultiFile(ui.tabs.Tab):
    def __init__(self,node):
        super().__init__(ui.mainui,node,'assets/tabmultifile.ui')

        self.w.getinitial.clicked.connect(self.getInitial)
        self.w.filters.textChanged.connect(self.filtersChanged)
        self.w.filelist.activated.connect(self.itemActivated)
        self.w.filterpat.editingFinished.connect(self.patChanged)
        self.w.mult.currentTextChanged.connect(self.multChanged)

        # all the files in the current directory (which match the filters)
        self.allFiles=[]
        self.onNodeChanged()
        
    def getInitial(self):
        # select a directory
        res = QtWidgets.QFileDialog.getExistingDirectory(ui.mainui,'Directory for images','.')
        if res!='':
            self.selectDir(res)

    def selectDir(self,dir):
        # called when we want to load a new directory, or when the node has changed (on loading)
        if self.node.dir != dir: # if the directory has changed reset the selected file list
            self.node.files=[]
            self.node.type.clearImages(self.node)
        self.w.dir.setText(dir)
        # get all the files in dir which are images
        self.allFiles = sorted([f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))
            and IMAGETYPERE.match(f) is not None])
        # using the relative path (usually more right than using the absolute)
        self.node.dir = os.path.relpath(dir)
        # rebuild the model
        self.buildModel()
        
    def patChanged(self):
        self.node.filterpat=self.w.filterpat.text()
        self.node.perform()
         
    def filtersChanged(self,t):
        # rebuild the filter list from the comma-sep string and rebuild the model
        self.node.namefilters=t.split(",")
        self.buildModel()
        
    def multChanged(self,s):
        try:
            self.node.mult=float(s)
            self.node.perform()
        except:
            ui.mainui.error("Bad mult string in 'multifile': "+s)

    def onNodeChanged(self):
        # the node has changed - set the filters text widget and reselect the dir.
        # This will only clear the selected files if we changed the dir.
        self.w.filters.setText(",".join(self.node.namefilters))
        self.selectDir(self.node.dir)
        s=""
        for i in range(len(self.node.files)):
            s+="{}:\t{}\n".format(i,self.node.files[i])
#        s+="\n".join([str(x) for x in self.node.imgpaths])
        self.w.outputFiles.setPlainText(s)
        i = self.w.mult.findText(str(int(self.node.mult)))
        self.w.mult.setCurrentIndex(i)
        self.w.filterpat.setText(self.node.filterpat)
                    
    def buildModel(self):
        # build the model that the list view uses
        self.model = QtGui.QStandardItemModel(self.w.filelist)
        for x in self.allFiles:
           add=True
           for f in self.node.namefilters:
               if not f in x:
                   add=False # only add a file if all the filters are present
                   break
           if add:
               # create a checkable item for each file, and check the checkbox
               # if it is in the files list
               item = QtGui.QStandardItem(x)
               item.setCheckable(True)
               if x in self.node.files:
                   item.setCheckState(Qt.Checked)
               self.model.appendRow(item)
               
        self.w.filelist.setModel(self.model)
        self.model.dataChanged.connect(self.checkedChanged)
        
    def itemActivated(self,idx):
        # called when we "activate" an item, typically by doubleclicking: load the file
        # to preview it
        item = self.model.itemFromIndex(idx)
        path = os.path.join(self.node.dir,item.text())
        source = (path,self.node.type.getFilterName(self.node,path))
        img = Image.load(path,source)
        img.img *= self.node.mult
        self.w.canvas.display(img)
        
        
    def checkedChanged(self):
        # the checked items have changed, reset the list and regenerate
        # the files list
        self.node.files=[]
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.checkState()==Qt.Checked:
                self.node.files.append(item.text())
        self.node.perform()        
