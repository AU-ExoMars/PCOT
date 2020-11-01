from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt,QCommandLineOption,QCommandLineParser
import os,sys,traceback,json,time,getpass
from typing import List, Set, Dict, Tuple, Optional, Any, OrderedDict, ClassVar

import ui
import ui.tabs,ui.help,ui.namedialog
import xform
import macros
import graphview,palette,graphscene
import filters

def getUserName():
    if 'PCOT_USER' in os.environ:
        return os.environ['PCOT_USER']
    else:
        return getpass.getuser()
        
class MainUI: # annoying forward decl for type hints
    pass
    
class MainUI(ui.tabs.DockableTabWindow):
    windows: ClassVar[List[MainUI]]         # list of all windows
    graph: xform.XFormGraph                 # the graph I am showing
    macroPrototype: macros.XFormMacro       # if I am showing a macro, the macro prototype (else None)
    view: graphview.GraphView               # my view of the scene (which is in the graph)
    tabs: OrderedDict[str,ui.tabs.Tab]      # inherited from DockableTabWindow, dict of tabs by title
    saveFileName: str                       # if I have saved/loaded, the name of the file
    camera: str                             # camera type (PANCAM/AUPE)
    captionType: int                        # caption type for images (index into combobox)
    palette: palette.Palette                # the node palette on the right
    
    # (most UI elements omitted)
    tabWidget: QtWidgets.QTabWidget         # container for tabs
    extraCtrls: QtWidgets.QWidget           # containing for macro controls
    


    windows = [] # list of all main windows open
    def __init__(self,macroWindow=False):
        super().__init__()
        self.graph = None
        uic.loadUi('assets/main.ui',self)
        self.initTabs()
        self.saveFileName = None
        self.setWindowTitle(ui.app.applicationName()+' '+ui.app.applicationVersion())

        self.setCamera("PANCAM")
        self.setCaption(0)        
        
        # connect buttons etc.        
        self.autolayoutButton.clicked.connect(self.autoLayoutButton)
        self.dumpButton.clicked.connect(lambda: self.graph.dump())
        self.capCombo.currentIndexChanged.connect(self.captionChanged)
        self.camCombo.currentIndexChanged.connect(self.cameraChanged)
        self.actionSave_As.triggered.connect(self.saveAsAction)
        self.action_New.triggered.connect(self.newAction)
        self.actionNew_Macro.triggered.connect(self.newMacroAction)
        self.actionSave.triggered.connect(self.saveAction)
        self.actionOpen.triggered.connect(self.openAction)
        self.actionCopy.triggered.connect(self.copyAction)
        self.actionPaste.triggered.connect(self.pasteAction)
        self.actionCut.triggered.connect(self.cutAction)
        
        # get and activate the status bar        
        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # set up the scrolling palette and make the buttons therein
        self.palette = palette.Palette(self.paletteArea,self.paletteContents,self.view)


        if macroWindow:        
            # and remove some things which don't apply to macro windows
            self.menuFile.setEnabled(False)
            self.capCombo.setVisible(False)
            self.camCombo.setVisible(False)
            self.camlabel.setVisible(False)
            self.caplabel.setVisible(False)
            # add some extra widgets
            b = QtWidgets.QPushButton("Add input")
            b.pressed.connect(self.addMacroInput)
            self.extraCtrls.layout().addWidget(b,0,0)
            b = QtWidgets.QPushButton("Add output")
            b.pressed.connect(self.addMacroOutput)
            self.extraCtrls.layout().addWidget(b,0,1)
            b = QtWidgets.QPushButton("Rename macro")
            b.pressed.connect(self.renameMacro)
            self.extraCtrls.layout().addWidget(b,0,2)
        else:
            self.reset() # create empty "standard" graph
            self.macroPrototype = None # we are not a macro

        # make sure the view has a link up to this window,
        # also will tint the view if we are a macro
        self.view.setWindow(self,macroWindow)

        self.show()
        ui.msg("OK")
        if graphscene.hasGrandalf:
            ui.log("Grandalf found.")
        else:
            ui.log("Grandalf not found - autolayout will be rubbish")
        MainUI.windows.append(self)    
        
    def isMacro(self):
        # these two had better agree!
        assert (self.macroPrototype is not None) == self.graph.isMacro
        return self.graph.isMacro
        
    def scene(self):
        return self.graph.scene

    @staticmethod
    def createMacroWindow(proto,isNewMacro):
        w = MainUI(True) # create macro window
        # link the window to the prototype
        w.macroPrototype = proto
        w.graph = proto.graph
        w.setWindowTitle(ui.app.applicationName()+
            ' '+ui.app.applicationVersion()+
            " [MACRO {}]".format(proto.name))
        w.graph.constructScene(isNewMacro) # builds the scene
        w.view.setScene(w.graph.scene)
        
    # run through all the palettes on all main windows,
    # repopulating them. Done typically when macros are added and removed.
    @staticmethod
    def rebuildPalettes():
        for w in MainUI.windows:
            w.palette.populate()

    # rebuild the graphics in all main windows and also all the tab titles
    # (since they may have been renamed)
    @staticmethod
    def rebuildAll():
        for w in MainUI.windows:
            w.graph.scene.rebuild()
            w.retitleTabs()

    def closeEvent(self,evt):
        MainUI.windows.remove(self)
        
    def autoLayoutButton(self):
        self.graph.constructScene(True)
        self.view.setScene(self.graph.scene)
        
    # create a dictionary of everything in the app we need to save: global settings,
    # the graph, macros etc.
    def serialise(self):
        d={}
        d['SETTINGS'] = {'cam':self.camera,'cap':self.captionType}
        d['INFO'] = {'author':getUserName(),'date':time.time()}
        d['GRAPH'] = self.graph.serialise()
        # now we also have to serialise the macros
        d['MACROS'] = macros.XFormMacro.serialiseAll()
        return d
            
    
    # deserialise everything from the given top-level dictionary
    def deserialise(self,d):
        # deserialise macros before graph!
        if 'MACROS' in d:
            macros.XFormMacro.deserialiseAll(d['MACROS'])
        self.graph.deserialise(d['GRAPH'],True) # True to delete existing nodes first

        settings = d['SETTINGS']
        self.setCamera(settings['cam'])
        self.setCaption(settings['cap'])
        self.graph.perform() # and rerun everything
        
    def save(self,fname):
        # we serialise to a string and then save the string rather than
        # doing it in one step, to avoid errors in the former leaving us
        # with an unreadable file.
        try:
            d = self.serialise()
            s = json.dumps(d,sort_keys=True,indent=4)
            try:
                with open(fname,'w') as f:
                        f.write(s)
            except Exception as e:
                ui.error("cannot save file {}: {}".format(fname,e))
            ui.msg("File saved")
        except Exception as e:
            traceback.print_exc()
            ui.error("cannot generate save data: {}".format(e))
    
    def load(self,fname):
        try:
            with open(fname) as f:
                d = json.load(f)
                self.deserialise(d)
                # now we need to reconstruct the scene with the new data
                # (False means don't do autolayout, read xy data from the dict instead)
                self.graph.constructScene(False)
                self.view.setScene(self.graph.scene)
                ui.msg("File loaded")
                self.saveFileName = fname
        except Exception as e:
            traceback.print_exc()
            ui.error("cannot open file {}: {}".format(fname,e))
        
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
        self.graph.scene.copy()
    def pasteAction(self):
        self.graph.scene.paste()
    def cutAction(self):
        self.graph.scene.cut()
            
    def newAction(self):
        MainUI() # create a new empty window
        
    def newMacroAction(self):
        p=macros.XFormMacro(None)
        MainUI.createMacroWindow(p,True)
        
    def reset(self):
        # create a dummy graph with just a source
        self.graph = xform.XFormGraph(False)
        source = self.graph.create("rgbfile")
        self.saveFileName = None
        # set up its scene and view
        self.graph.constructScene(True)
        self.view.setScene(self.graph.scene)
        
        

    # this gets called from way down in the scene to open tabs for nodes
    def openTab(self,node):
        # has the node got a tab open IN THIS WINDOW?
        tab=None
        for x in node.tabs:
            if x.window == self:
                tab = x
        # nope, ask the node type to make one
        if tab is None:
            tab = node.type.createTab(node,self)
            if tab is not None:
                node.tabs.append(tab)
        # pull the tab to the front (either the newly created one
        # or the one we already had)
        if tab is not None:
            self.tabWidget.setCurrentWidget(tab)
    
    # tab changed (this is connected up in the superclass)
    def currentChanged(self,index): # index is ignored
        if self.tabWidget.currentWidget() is None:
            # we've expanded or closed all widgets
            w = None
        else:
            w = self.tabWidget.currentWidget().node
        self.graph.scene.currentChanged(w)
            
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
        
    def addMacroConnector(self,type):
        # create the node inside the prototype
        n = self.graph.create(type)
        n.conntype = 'any'
        n.xy = self.graph.scene.getNewPosition()
        assert(self.isMacro())
        assert(self.macroPrototype is not None)
        n.proto = self.macroPrototype
        # reset the connectors
        n.proto.setConnectors()
        # rebuild the visual components inside the prototype
        self.graph.scene.rebuild()
        # we also have to rebuild any graphs the macro is in, because
        # the number of connectors will have changed.
        for inst in n.proto.instances:
            inst.graph.scene.rebuild()
        
    def addMacroInput(self):
        self.addMacroConnector('in')
        
    def addMacroOutput(self):
        self.addMacroConnector('out')
        
    def renameMacro(self):
        assert(self.isMacro())
        assert(self.macroPrototype is not None)
        changed,newname=ui.namedialog.do(self.macroPrototype.name)
        if changed:
            self.macroPrototype.renameType(newname)
        
    def performAll(self):
        if self.graph is not None:
            self.graph.perform()
        
