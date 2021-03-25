## @package ui.mainwindow
# Code for the main windows, which hold a scene representing the 
# "patch" or a macro prototype, a palette of transforms, and an area
# for tabs controlling transforms.

import getpass
import json
import os
import time
import traceback
from typing import List, Optional, OrderedDict, ClassVar

from PyQt5 import QtWidgets, uic, QtGui
from PyQt5.QtCore import Qt

from ui import graphscene, graphview
import macros
import palette
import ui
import ui.help
import ui.namedialog
import ui.tabs
import xform


## return the current username, whichis either obtained from the OS
# or from the PCOT_USER environment variable

def getUserName():
    if 'PCOT_USER' in os.environ:
        return os.environ['PCOT_USER']
    else:
        return getpass.getuser()


class InputSelectButton(QtWidgets.QPushButton):
    def __init__(self, n, inp):
        text = "Input " + str(n)
        self.input = inp
        super().__init__(text=text)
        self.clicked.connect(lambda: self.input.openWindow())


class HelpWindow(QtWidgets.QDialog):
    def __init__(self, parent, node):
        super().__init__(parent=parent)
        self.setModal(True)
        node.helpwin = self
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        layout = QtWidgets.QVBoxLayout(self)
        txt = ui.help.getHelpHTML(node.type, node.error)
        self.setWindowTitle("Help for '{}'".format(node.type.name))
        wid = QtWidgets.QLabel()
        wid.setText(txt)
        layout.addWidget(wid)

#        button = QtWidgets.QPushButton("Close")
#        button.clicked.connect(lambda: self.close())
#        layout.addWidget(button)

        self.show()


## The main window class
class MainUI(ui.tabs.DockableTabWindow):
    ## @var windows
    # list of all windows
    windows: ClassVar[List['MainUI']]

    ## @var graph
    # the graph I am showing - might be None, but only briefly, when creating a window for a macro prototype
    graph: Optional[xform.XFormGraph]

    ## @var macroPrototype
    # if I am showing a macro, the macro prototype (else None)
    macroPrototype: Optional[macros.XFormMacro]

    ## @var view
    # my view of the scene (representing the graph)
    view: graphview.GraphView

    ## @var tabs
    # inherited from DockableTabWindow, dict of tabs by title
    tabs: OrderedDict[str, ui.tabs.Tab]

    ## @var saveFileName
    # if I have saved/loaded, the name of the file
    saveFileName: Optional[str]

    ## @var camera
    # camera type (PANCAM/AUPE)
    camera: str

    ## @var palette
    # the node palette on the right
    palette: palette.Palette

    # (most UI elements omitted)

    ## @var tabWidget
    # container for tabs
    tabWidget: QtWidgets.QTabWidget

    ## @var extraCtrls
    # containing for macro controls
    extraCtrls: QtWidgets.QWidget

    windows = []  # list of all main windows open

    ## constructor, takes true if is for a macro prototype
    def __init__(self, macroWindow=False):
        super().__init__()
        self.graph = None
        uic.loadUi('assets/main.ui', self)
        self.initTabs()
        self.saveFileName = None
        self.setWindowTitle(ui.app.applicationName() + ' ' + ui.app.applicationVersion())

        # connect buttons etc.
        self.autolayoutButton.clicked.connect(self.autoLayoutButton)
        self.dumpButton.clicked.connect(lambda: self.graph.dump())
        self.capCombo.currentIndexChanged.connect(self.captionChanged)
        self.actionSave_As.triggered.connect(self.saveAsAction)
        self.action_New.triggered.connect(self.newAction)
        self.actionNew_Macro.triggered.connect(self.newMacroAction)
        self.actionSave.triggered.connect(self.saveAction)
        self.actionOpen.triggered.connect(self.openAction)
        self.actionCopy.triggered.connect(self.copyAction)
        self.actionPaste.triggered.connect(self.pasteAction)
        self.actionCut.triggered.connect(self.cutAction)
        self.runAllButton.pressed.connect(self.runAllAction)
        self.autoRun.toggled.connect(self.autorunChanged)

        # get and activate the status bar        
        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)

        # set up the scrolling palette and make the buttons therein
        self.palette = palette.Palette(self.paletteArea, self.paletteContents, self.view)

        # and remove some things which don't apply to macro windows
        if macroWindow:
            # first turn off the file menu
            self.menuFile.setEnabled(False)
            # annoyingly have to do this too, or we'll still be able
            # to use kbd shortcuts!
            for action in self.menuFile.actions():
                action.setEnabled(False)

            self.capCombo.setVisible(False)
            self.caplabel.setVisible(False)
            # add some extra widgets
            b = QtWidgets.QPushButton("Add input")
            b.pressed.connect(self.addMacroInput)
            self.extraCtrls.layout().addWidget(b, 0, 0)
            b = QtWidgets.QPushButton("Add output")
            b.pressed.connect(self.addMacroOutput)
            self.extraCtrls.layout().addWidget(b, 0, 1)
            b = QtWidgets.QPushButton("Rename macro")
            b.pressed.connect(self.renameMacro)
            self.extraCtrls.layout().addWidget(b, 0, 2)
        else:
            self.reset()  # create empty "standard" graph
            self.macroPrototype = None  # we are not a macro
            # now create the input selector buttons
            isfLayout = QtWidgets.QHBoxLayout()
            self.inputSelectorFrame.setLayout(isfLayout)
            for x in range(0, len(self.graph.inputMgr.inputs)):
                isfLayout.addWidget(InputSelectButton(x, self.graph.inputMgr.inputs[x]))

        # make sure the view has a link up to this window,
        # also will tint the view if we are a macro
        self.view.setWindow(self, macroWindow)
        # This only does something when you already have a graph, which macro protos don't,
        # but that's OK because they don't have a caption control either.
        self.setCaption(0)

        self.show()
        ui.msg("OK")
        if graphscene.hasGrandalf:
            ui.log("Grandalf found.")
        else:
            ui.log("Grandalf not found - autolayout will be rubbish")
        MainUI.windows.append(self)
        MainUI.updateAutorun()

    ## is this a macro?
    def isMacro(self):
        # these two had better agree!
        assert (self.macroPrototype is not None) == self.graph.isMacro
        return self.graph.isMacro

    ## return the scene (stored in the graph)
    def scene(self):
        return self.graph.scene

    ## create a new macro window - pass true when this is a new macro.
    @staticmethod
    def createMacroWindow(proto, isNewMacro):
        w = MainUI(True)  # create macro window
        # link the window to the prototype
        w.macroPrototype = proto
        w.graph = proto.graph
        w.setWindowTitle(ui.app.applicationName() +
                         ' ' + ui.app.applicationVersion() +
                         " [MACRO {}]".format(proto.name))
        w.graph.constructScene(isNewMacro)  # builds the scene
        w.view.setScene(w.graph.scene)

    ## run through all the palettes on all main windows,
    # repopulating them. Done typically when macros are added and removed.
    @staticmethod
    def rebuildPalettes():
        for w in MainUI.windows:
            w.palette.populate()

    ## rebuild the graphics in all main windows and also all the tab titles
    # (since they may have been renamed)
    @staticmethod
    def rebuildAll():
        for w in MainUI.windows:
            w.graph.scene.rebuild()
            w.retitleTabs()

    ## close event handler
    def closeEvent(self, evt):
        MainUI.windows.remove(self)
        self.graph.inputMgr.closeAllWindows()

    ## autolayout button handler
    def autoLayoutButton(self):
        self.graph.constructScene(True)
        self.view.setScene(self.graph.scene)

    ## create a dictionary of everything in the app we need to save: global settings,
    # the graph, macros etc.
    def serialise(self):
        d = {'SETTINGS': {'cap': self.graph.captionType},
             'INFO': {'author': getUserName(),
                      'date': time.time()},
             'GRAPH': self.graph.serialise(),
             'INPUTS': self.graph.inputMgr.serialise(),
             'MACROS': macros.XFormMacro.serialiseAll()}
        # now we also have to serialise the macros
        return d

    ## deserialise everything from the given top-level dictionary.
    # Deserialising the inputs is optional : we don't do it if we are loading templates
    # or if there is no INPUTS entry in the file, or there's no input manager (shouldn't
    # happen unless we're doing something weird like loading a macro prototype graph)
    def deserialise(self, d, deserialiseInputs=True):
        # deserialise macros before graph!
        if 'MACROS' in d:
            macros.XFormMacro.deserialiseAll(d['MACROS'])
        self.graph.deserialise(d['GRAPH'], True)  # True to delete existing nodes first

        if 'INPUTS' in d and deserialiseInputs and self.graph.inputMgr is not None:
            self.graph.inputMgr.deserialise(d['INPUTS'])

        settings = d['SETTINGS']
        self.setCaption(settings['cap'])
        self.graph.changed()  # and rerun everything

    ## saving to a file  
    def save(self, fname):
        # we serialise to a string and then save the string rather than
        # doing it in one step, to avoid errors in the former leaving us
        # with an unreadable file.
        try:
            d = self.serialise()
            s = json.dumps(d, sort_keys=True, indent=4)
            try:
                with open(fname, 'w') as f:
                    f.write(s)
            except Exception as e:
                ui.error("cannot save file {}: {}".format(fname, e))
            ui.msg("File saved : " + fname)
        except Exception as e:
            traceback.print_exc()
            ui.error("cannot generate save data: {}".format(e))

    ## loading from a file
    def load(self, fname):
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
            ui.error("cannot open file {}: {}".format(fname, e))

    ## the "save as" menu handler
    def saveAsAction(self):
        res = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', '.', "JSON files (*.json)")
        if res[0] != '':
            self.save(res[0])
            self.saveFileName = res[0]

    ## the "save" menu handler
    def saveAction(self):
        if self.saveFileName is None:
            self.saveAsAction()
        else:
            self.save(self.saveFileName)

    ## the "open" menu handler
    def openAction(self):
        res = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', '.', "JSON files (*.json)")
        if res[0] != '':
            self.closeAllTabs()
            self.load(res[0])

    ## "copy" menu/keypress
    def copyAction(self):
        self.graph.scene.copy()

    ## "paste" menu/keypress
    def pasteAction(self):
        self.graph.scene.paste()

    ## "cut menu/keypress
    def cutAction(self):
        self.graph.scene.cut()

    ## "run all" action, typically used when you have auto-run turned off (editing a macro,
    # perhaps)
    def runAllAction(self):
        self.runAll()

    ## "new" menu/keypress, will create a new top-level "patch"
    def newAction(self):
        MainUI()  # create a new empty window

    ## "new macro" menu/keypress, will create a new macro prototype stored
    # in this patch
    def newMacroAction(self):
        p = macros.XFormMacro(None)
        MainUI.createMacroWindow(p, True)

    ## create a new dummy graph with a single source
    def reset(self):
        # create a dummy graph with just a source
        self.graph = xform.XFormGraph(False)
        source = self.graph.create("input 0")
        self.saveFileName = None
        # set up its scene and view
        self.graph.constructScene(True)
        self.view.setScene(self.graph.scene)

    ## this gets called from way down in the scene to open tabs for nodes
    def openTab(self, node):
        # has the node got a tab open IN THIS WINDOW?
        tab = None
        for x in node.tabs:
            if x.window == self:
                tab = x
        # nope, ask the node type to make one
        if tab is None:
            tab = node.type.createTab(node, self)
            if tab is not None:
                node.tabs.append(tab)
        # pull the tab to the front (either the newly created one
        # or the one we already had)
        if tab is not None:
            self.tabWidget.setCurrentWidget(tab)
            # tell the tab to update its error state
            tab.updateError()

    ## tab changed (this is connected up in the superclass)
    def currentChanged(self, index):  # index is ignored
        if self.tabWidget.currentWidget() is None:
            # we've expanded or closed all widgets
            w = None
        else:
            w = self.tabWidget.currentWidget().node
        self.graph.scene.currentChanged(w)

    ## caption type has been changed in widget
    def captionChanged(self, i):
        self.graph.captionType = i  # best stored as an int, I think
        self.graph.performNodes()

    ## set the caption type (for actual main windows, not macros)
    def setCaption(self, i):
        if self.graph is not None:
            self.graph.captionType = i
            self.capCombo.setCurrentIndex(i)

    ## autorun has been changed in widget. This is global,
    # so all windows must agree.
    def autorunChanged(self, i):
        xform.XFormGraph.autoRun = self.autoRun.isChecked()
        # I'll set autorun on all graphs
        MainUI.updateAutorun()
        # but only rerun this one
        if xform.XFormGraph.autoRun:
            self.runAll()

    ## update autorun checkbox states from class variable
    @staticmethod
    def updateAutorun():
        for w in MainUI.windows:
            print("Setting autorun to ", xform.XFormGraph.autoRun)
            w.autoRun.setChecked(xform.XFormGraph.autoRun)

    ## open a window showing help for a node
    def openHelp(self, node):
        if node.helpwin is not None:
            node.helpwin.close()  # close existing window you may have left open :)
        win = HelpWindow(self, node)

    ## add a macro connector, only should be used on macro prototypes   
    def addMacroConnector(self, type):
        # create the node inside the prototype
        n = self.graph.create(type)
        n.conntype = 'any'
        n.xy = self.graph.scene.getNewPosition()
        assert (self.isMacro())
        assert (self.macroPrototype is not None)
        n.proto = self.macroPrototype
        # reset the connectors
        n.proto.setConnectors()
        # rebuild the visual components inside the prototype
        self.graph.scene.rebuild()
        # we also have to rebuild any graphs the macro is in, because
        # the number of connectors will have changed.
        for inst in n.proto.instances:
            inst.graph.scene.rebuild()

    ## add a macro in connector, only should be used on macro prototypes   
    def addMacroInput(self):
        self.addMacroConnector('in')

    ## add a macro out connector, only should be used on macro prototypes   
    def addMacroOutput(self):
        self.addMacroConnector('out')

    ## opens a dialog to rename a macro, called on "rename macro" UI
    def renameMacro(self):
        assert (self.isMacro())
        assert (self.macroPrototype is not None)
        changed, newname = ui.namedialog.do(self.macroPrototype.name)
        if changed:
            self.macroPrototype.renameType(newname)

    ## perform all in the graph
    def runAll(self):
        if self.graph is not None:
            self.graph.changed()
