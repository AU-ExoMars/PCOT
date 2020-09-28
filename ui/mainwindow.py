from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt,QCommandLineOption,QCommandLineParser
import os,sys,traceback,json,time,getpass

import ui.tabs,ui.help
import xform
import graphview,palette,graphscene
import filters

def getUserName():
    if 'PCOT_USER' in os.environ:
        return os.environ['PCOT_USER']
    else:
        return getpass.getuser()

class MainUI(ui.tabs.DockableTabWindow):
    def autoLayout(self):
        # called autoLayout, because that's essentially the end-user
        # visible action. Will delete the old scene and create a new scene,
        # linking the viewer to it.
        self.scene = graphscene.XFormGraphScene(self,True)
        
    # create a dictionary of everything in the app we need to save: global settings,
    # the graph, macros etc.
    def serialise(self):
        d={}
        d['SETTINGS'] = {'cam':self.camera,'cap':self.captionType}
        d['INFO'] = {'author':getUserName(),'date':time.time()}
        d['GRAPH'] = self.graph.serialise()
        return d
            
    
    # deserialise everything from the given top-level dictionary
    def deserialise(self,d):
        settings = d['SETTINGS']
        self.graph.deserialise(d['GRAPH'],True) # True to delete existing nodes first

        self.setCamera(settings['cam'])
        self.setCaption(settings['cap'])
        self.graph.downRecursePerform() # and rerun everything
        
    def save(self,fname):
        # we serialise to a string and then save the string rather than
        # doing it in one step, to avoid errors in the former leaving us
        # with an unreadable file.
        try:
            with open(fname,'w') as f:
                d = self.serialise()
                s = json.dumps(d,sort_keys=True,indent=4)
                f.write(s)
                self.msg("File saved")
        except Exception as e:
            traceback.print_exc()
            self.error("cannot save file {}: {}".format(fname,e))
    
    def load(self,fname):
        try:
            with open(fname) as f:
                d = json.load(f)
                self.deserialise(d)
                # now we need to reconstruct the scene with the new data
                # (False means don't do autolayout, read xy data from the dict instead)
                self.scene = graphscene.XFormGraphScene(self,False)
                self.msg("File loaded")
                self.saveFileName = fname
        except Exception as e:
            traceback.print_exc()
            self.error("cannot open file {}: {}".format(fname,e))
        
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
            
    def copyAction(self):
        self.scene.copy()
    def pasteAction(self):
        self.scene.paste()
    def cutAction(self):
        self.scene.cut()
            
    def newAction(self):
        # create a dummy graph with just a source
        self.graph=xform.XFormGraph()
        source = self.graph.create("rgbfile")
        self.saveFileName = None
        # set up its scene and view
        self.autoLayout() # builds the scene
        

    def msg(self,t): # show msg on status bar
        self.statusBar.showMessage(t)
        
    def log(self,s):
        print("LOG:",s)
        self.logText.append(s)
        
    def error(self,s):
        self.app.beep()
#        traceback.print_stack()
        self.msg("Error: {}".format(s))
        self.log('<font color="red">Error: </font> {}'.format(s))
        
    def warn(self,s):
        self.app.beep()
        QtWidgets.QMessageBox.warning(self,'WARNING',s)
        
    def logXFormException(self,node,e):
        self.app.beep()
        self.error("Exception in {}: {}".format(node.name,e))
        self.log('<font color="red">Exception in <b>{}</b>: </font> {}'.format(node.name,e))
        
    # called when a graph saved with a different version of a node is loaded
    def versionWarn(self,n):
        self.log('<font color="red">Version clash</font> in node \'{}\', type \'{}\'. Current: {}, file: {}'
            .format(n.name,n.type.name,n.type.ver,n.savedver))
        self.log('<font color="blue">Current MD5 hash: </font> {}'.format(n.type.md5()))
        self.log('<font color="blue">MD5 hash in file:</font> {}'.format(n.savedmd5))
        
        self.warn(
        """
Node '{}' was saved with a different version of the '{}' node's code.
Current version: {}
Version in file: {}
If these are the same the file may have been modified without changing the \
version numbers. See MD5 data in the log.
        """
        .format(n.name,n.type.name,n.type.ver,n.savedver))
        
    def __init__(self,app):
        super().__init__()
        self.app = app
        self.graph = None
        ui.mainui = self
        uic.loadUi('assets/main.ui',self)
        self.initTabs()
        self.saveFileName = None
        self.setWindowTitle(app.applicationName()+' '+app.applicationVersion())

        self.setCamera("PANCAM")
        self.setCaption(0)        
        
        # connect buttons etc.        
        self.autolayoutButton.clicked.connect(self.autoLayout)
        self.dumpButton.clicked.connect(lambda: self.graph.dump())
        self.capCombo.currentIndexChanged.connect(self.captionChanged)
        self.camCombo.currentIndexChanged.connect(self.cameraChanged)
        self.actionSave_As.triggered.connect(self.saveAsAction)
        self.action_New.triggered.connect(self.newAction)
        self.actionSave.triggered.connect(self.saveAction)
        self.actionOpen.triggered.connect(self.openAction)
        self.actionCopy.triggered.connect(self.copyAction)
        self.actionPaste.triggered.connect(self.pasteAction)
        self.actionCut.triggered.connect(self.cutAction)
        
        # get and activate the status bar        
        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)

        
        # set up the scrolling palette and make the buttons therein
        palette.setup(self.paletteArea,self.paletteContents,self.view)

        self.newAction() # create empty graph

        self.show()
        self.msg("OK")
        if graphscene.hasGrandalf:
            self.log("Grandalf found.")
        else:
            self.log("Grandalf not found - autolayout will be rubbish")

    # this gets called from way down in the scene to open tabs for nodes
    def openTab(self,node):
        # has the node got a tab open already?
        if node.tab is None:
            # nope, ask the node type to make one (will set node.tab)
            node.type.createTab(node)
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
            
    def captionChanged(self,i):
        self.captionType = i # best stored as an int, I think
        
    def setCaption(self,i):
        self.captionType = i
        self.capCombo.setCurrentIndex(i)
        
    def cameraChanged(self,i):
        self.camera = self.camCombo.currentText()
        self.performAll()
        
    def setCamera(self,cam):
        i = self.camCombo.findText(cam)
        if i>=0:
            self.camera = cam
            self.camCombo.setCurrentIndex(i)
            self.performAll()

    # open a window showing help for a node
    def openHelp(self,node):
        if node.helpwin is not None:
            node.helpwin.close() # close existing window you may have left open :)
        win = QtWidgets.QMainWindow()
        wid = QtWidgets.QLabel()
        win.setCentralWidget(wid)
        win.setWindowTitle("Help for '{}'".format(node.type.name))
        node.helpwin = win # just to stop GC
        txt = ui.help.help(node.type)
        wid.setText(txt)
        win.setMinimumSize(400,50)
        win.show()
        
    def performAll(self):
        if self.graph is not None:
            self.graph.downRecursePerform()
        
