"""
Code for the main windows, which hold a scene representing the
"patch" or a macro prototype, a palette of transforms, and an area
for tabs controlling transforms.
"""
import logging
import os
import traceback
from string import Template
from typing import List, Optional, OrderedDict, ClassVar, Dict

import markdown
from PySide2 import QtWidgets
from PySide2.QtCore import Qt
from PySide2.QtGui import QTextCursor
from PySide2.QtWidgets import QAction, QMessageBox, QDialog, QMenu

import pcot
from pcot.ui import graphscene, graphview, uiloader
import pcot.macros as macros
import pcot.palette as palette
import pcot.ui as ui
import pcot.ui.namedialog as namedialog
import pcot.ui.tabs as tabs
import pcot.xform as xform
from pcot.ui.help import HelpWindow
from pcot.utils import SignalBlocker

logger = logging.getLogger(__name__)


class InputSelectButton(QtWidgets.QPushButton):
    def __init__(self, n, inp):
        text = f"Input {n}"
        self.input = inp
        super().__init__(text=text)
        self.clicked.connect(lambda: self.input.openWindow())


## The main window class
class MainUI(ui.tabs.DockableTabWindow):
    ## @var windows
    # list of all windows
    windows: ClassVar[List['MainUI']]

    ## @var graph
    # the graph I am showing - might be the main graph of the document
    # or one of its macros
    graph: Optional[xform.XFormGraph]

    ## @var doc
    # backpointer to the document of which I am a part
    doc: 'Document'

    ## @var macroPrototype
    # if I am showing a macro, the macro prototype (else None)
    macroPrototype: Optional['macros.XFormMacro']

    ## @var view
    # my view of the scene (representing the graph)
    view: graphview.GraphView

    ## @var tabs
    # inherited from DockableTabWindow, dict of tabs by title
    tabs: OrderedDict[str, ui.tabs.Tab]

    ## @var saveFileName
    # if I have saved/loaded, the name of the file
    saveFileName: Optional[str]

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

    # list of menu title->menu (findChildren should work to find a menu in a menu bar, but doesn't seem to).
    menus: Dict[str, QMenu]

    # QActions for recent file list
    recentActs: List[QAction] = []

    windows = []  # list of all main windows open

    def __init__(self,
                 doc=None,  # XFormMacro
                 macro=None,  # Document
                 doAutoLayout: bool = True):
        """Constructor which just calls _init()"""
        super().__init__()
        uiloader.loadUi('main.ui', self)
        # connect buttons etc.
        self.autolayoutButton.clicked.connect(self.autoLayoutButton)
        # self.dumpButton.clicked.connect(lambda: self.graph.dump())
        self.fitButton.clicked.connect(self.fitClicked)
        self.capCombo.currentIndexChanged.connect(self.captionChanged)
        self.annotalphaSlider.sliderReleased.connect(self.annotalphaChanged)

        self.action_New.triggered.connect(self.newAction)
        self.actionNew_Macro.triggered.connect(self.newMacroAction)
        self.actionSave.triggered.connect(self.saveAction)
        self.actionSave_As.triggered.connect(lambda: self.saveAsAction(True))
        self.actionSave_As_without_inputs.triggered.connect(lambda: self.saveAsAction(False))
        self.actionOpen.triggered.connect(self.openAction)
        self.actionCopy.triggered.connect(self.copyAction)
        self.actionPaste.triggered.connect(self.pasteAction)
        self.actionCut.triggered.connect(self.cutAction)
        self.actionUndo.triggered.connect(self.undoAction)
        self.actionRedo.triggered.connect(self.redoAction)
        self.actionAbout.triggered.connect(self.aboutAction)

        self.runAllButton.clicked.connect(self.runAllAction)
        self.autoRun.toggled.connect(self.autorunChanged)

        # get and activate the status bar
        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)
        self.menuFile.addSeparator()
        self.isfLayout = QtWidgets.QHBoxLayout()
        self.inputSelectorFrame.setLayout(self.isfLayout)
        self.initTabs()
        self.menus = {}  # we need to use a dict because findChildren doesn't seem to work right.

        self._init(doc=doc, macro=macro, doAutoLayout=doAutoLayout,initial=True)

    def _init(self,
              doc,  # Document
              macro=None,  # XFormMacro
              initial=False,     # are we actually opening the window or reinitialing?
              doAutoLayout: bool = True):
        """This is the 'real' constructor, which is a separate function so
        we can reinitialise. Doc must always be supplied; it's the document
        we are using. If there is no macro, we are viewing the main graph of
        the document. Otherwise we are viewing a macro inside the document."""

        if macro is not None:
            self.graph = macro.graph
        else:
            self.graph = doc.graph

        self.doc = doc
        self.capCombo.setCurrentIndex(self.doc.settings.captionType)

        with SignalBlocker(self.annotalphaSlider):
            self.annotalphaSlider.setValue(self.doc.settings.alpha)

        self.setWindowTitle(ui.app().applicationName() + ' ' + ui.app().applicationVersion())
        self.rebuildRecents()

        # set up the scrolling palette and make the buttons therein. The paletteArea
        # is a Collapser created in Designer.
        self.palette = palette.Palette(doc, self.paletteArea, self.view)

        # and remove some things which don't apply to macro windows
        if macro is not None:
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

            self.macroPrototype = macro
            self.setWindowTitle(ui.app().applicationName() +
                                ' ' + ui.app().applicationVersion() +
                                " [MACRO {}]".format(self.graph.proto.name))
        else:
            # We are definitely a main window
            self.macroPrototype = None  # we are not a macro
            # now create the input selector buttons, removing the old ones.
            # We do this by getting rid of the old layout so we can set a new one, by reparenting
            # the old layout into a temporary widget.
            QtWidgets.QWidget().setLayout(self.isfLayout)
            # then we create and set a new layout and add the items to it.
            self.isfLayout = QtWidgets.QHBoxLayout()
            self.inputSelectorFrame.setLayout(self.isfLayout)

            for x in range(0, len(self.doc.inputMgr.inputs)):
                self.isfLayout.addWidget(InputSelectButton(x, self.doc.inputMgr.inputs[x]))

        # make sure the view has a link up to this window,
        # also will tint the view if we are a macro
        self.view.setWindow(self, macro is not None)

        if initial:
            pcot.config.executeWindowHooks(self)

        self.show()
        ui.msg("OK")
        if graphscene.hasGrandalf:
            ui.log("Grandalf found.")
        else:
            ui.log("Grandalf not found - autolayout will be rubbish")
        MainUI.windows.append(self)

        self.saveFileName = None
        MainUI.updateAutorun()
        self.graph.constructScene(doAutoLayout)
        self.view.setScene(self.graph.scene)
        self.doc.clearUndo()

    @classmethod
    def getWindowsForDocument(cls, d):
        return [w for w in cls.windows if w.doc == d]

    def fitClicked(self):
        self.view.fitInView(self.graph.scene.sceneRect(), Qt.KeepAspectRatio)

    def rebuildRecents(self):
        # add recent files to menu, removing old ones first. Note that recent files must be at the end
        # of the menu for this to work!

        for act in MainUI.recentActs:
            self.menuFile.removeAction(act)
        MainUI.recentActs = []

        recents = pcot.config.getRecents()
        if len(recents) > 0:
            for x in recents:
                act = QAction(x, parent=self)
                act.setData(x)
                self.menuFile.addAction(act)
                act.triggered.connect(self.loadRecent)
                MainUI.recentActs.append(act)

    ## is this a macro?
    def isMacro(self):
        # these two had better agree!
        assert (self.macroPrototype is not None) == self.graph.isMacro
        return self.graph.isMacro

    ## return the scene (stored in the graph)
    def scene(self):
        return self.graph.scene

    ## run through all the palettes on all main windows,
    # repopulating them. Done typically when macros are added and removed.
    @staticmethod
    def rebuildPalettes():
        for w in MainUI.windows:
            logger.info(f"Rebuilding window {w}")
            w.palette.populate()

    ## rebuild the graphics in all main windows and also all the tab titles
    # (since they may have been renamed)
    @staticmethod
    def rebuildAll(scene=True, tab=True):
        for w in MainUI.windows:
            if scene:
                if w.graph.scene is not None:
                    w.graph.scene.rebuild()
            if tab:
                w.retitleTabs()

    ## close event handler - close all windows on confirmation if this is a main window, otherwise it's a macro - don't
    # bother confirming, just close this window.

    def closeEvent(self, evt):
        if self.isMacro():
            MainUI.windows.remove(self)
            evt.accept()
        elif QMessageBox.question(self, "Close graph", "Are you sure?",
                                  QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            MainUI.windows.remove(self)
            self.closeAllTabs()
            # if the only remaining windows at this point are macro windows, close them too.
            if all([x.isMacro() for x in MainUI.windows]):
                for x in MainUI.windows.copy():  # do on a copy because this recurses
                    x.close()
            evt.accept()
        else:
            evt.ignore()

    ## autolayout button handler
    def autoLayoutButton(self):
        self.graph.constructScene(True)
        self.view.setScene(self.graph.scene)
        self.rebuildPalettes()
        self.rebuildPalettes()
        self.rebuildPalettes()

    ## saving to a file  
    def save(self, fname, saveInputs=True):
        # we serialise to a string and then save the string rather than
        # doing it in one step, to avoid errors in the former leaving us
        # with an unreadable file.
        try:
            ui.msg(f"Saving to {fname}")
            self.doc.save(fname, saveInputs=saveInputs)
            ui.msg(f"File saved to {fname}")
            self.rebuildRecents()
        except Exception as e:
            traceback.print_exc()
            ui.error("cannot save file {}: {}".format(fname, e))

    ## loading from a file
    def load(self, fname):
        # As the scene is constructed, widgets are constantly changed - this typically triggers runs.
        # For that reason we turn off autorun temporarily when loading.
        oldAutoRun = self.graph.autoRun
        self.graph.autoRun = False
        try:
            import pcot.document
            ui.msg(f"Loading file {fname}...")
            d = pcot.document.Document(fname)
            MainUI.windows.remove(
                self)  # remove the existing entry for this window, we'll add it again in the next line
            self._init(doc=d, doAutoLayout=False)  # rerun window construction
            self.graph.changed()  # and rerun everything
            ui.msg("File loaded")
            self.saveFileName = fname
            self.rebuildRecents()
        except Exception as e:
            traceback.print_exc()
            ui.error(f"cannot open file {fname}: {repr(e)}")
        finally:
            self.graph.autoRun = oldAutoRun

    ## the "save as" menu handler
    def saveAsAction(self, saveInputs):
        res = QtWidgets.QFileDialog.getSaveFileName(self,
                                                    "Save file " if saveInputs else "Save file (WITHOUT INPUTS)",
                                                    os.path.expanduser(pcot.config.getDefaultDir('pcotfiles')),
                                                    "PCOT files (*.pcot)",
                                                    options=pcot.config.getFileDialogOptions())
        logger.debug(f"Dialog result: {res[0]}")
        if res[0] != '':
            path = res[0]
            (root, ext) = os.path.splitext(path)
            if ext != '.pcot':
                ext += '.pcot'
            path = root + ext

            logger.info(f"saving: {res[0]}")
            self.save(path, saveInputs=saveInputs)
            self.saveFileName = path
            ui.log("Document written to " + path)
            pcot.config.setDefaultDir('pcotfiles', os.path.dirname(os.path.realpath(res[0])))
        else:
            logger.info("Save cancelled")

    ## the "save" menu handler
    def saveAction(self):
        if self.saveFileName is None:
            self.saveAsAction(True)
        else:
            self.save(self.saveFileName)

    ## the "open" menu handler
    def openAction(self):
        ops = pcot.config.getFileDialogOptions()
        res = QtWidgets.QFileDialog.getOpenFileName(self,
                                                    'Open file',
                                                    os.path.expanduser(pcot.config.getDefaultDir('pcotfiles')),
                                                    "PCOT files (*.pcot)",
                                                    options=pcot.config.getFileDialogOptions())
        if res[0] != '':
            self.closeAllTabs()
            self.load(res[0])

    ## recent file load
    def loadRecent(self, _):
        act = self.sender()
        if act is not None:
            fn = act.data()
            self.closeAllTabs()
            self.load(fn)

    ## "copy" menu/keypress
    def copyAction(self):
        self.graph.scene.copy()

    ## "paste" menu/keypress
    def pasteAction(self):
        try:
            self.graph.scene.paste()
        except Exception as e:
            ui.error("Clipboard does not contain valid PCOT data")

    ## "cut menu/keypress
    def cutAction(self):
        self.graph.scene.cut()

    def undoAction(self):
        self.doc.undo()

    def redoAction(self):
        self.doc.redo()

    ## "run all" action, typically used when you have auto-run turned off (editing a macro,
    # perhaps)
    def runAllAction(self):
        self.runAll()

    ## "new" menu/keypress, will create a new top-level "patch"
    def newAction(self):
        import pcot.document
        d = pcot.document.Document()
        MainUI(d, doAutoLayout=True)  # create a new empty window

    ## "new macro" menu/keypress, will create a new macro prototype in this document
    def newMacroAction(self):
        self.doc.mark()
        p = macros.XFormMacro(self.doc, None)
        MainUI(self.doc, macro=p, doAutoLayout=True)

    def aboutAction(self):
        dialog = QDialog(self)
        uiloader.loadUi('about.ui', dialog)
        txt = Template(pcot.config.getAssetAsString('about.md')).substitute(version=pcot.__fullversion__)
        doc = dialog.textEdit.document()
        doc.setDefaultStyleSheet(pcot.config.getAssetAsString('about.css'))
        txt = markdown.markdown(txt)
        doc.setHtml(txt)
        dialog.textEdit.moveCursor(QTextCursor.Start)
        # print(dialog.textEdit.toHtml())
        dialog.show()

    def findOrAddMenu(self, name):
        """Find a menu or add a new one"""

        # this ought to work.
#        for m in self.menubar.findChildren(QMenu):
#            if m.objectName() == name or m.title() == name:
#                return m

        # but doesn't so we do this.
        if name in self.menus:
            return self.menus[name]

        m = QMenu(name)
        self.menus[name] = m
        self.menubar.addMenu(m)
        return m

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
        # the scene can be None sometimes if we are loading a new graph on top of an old one, and it thinks the
        # tabs have changed (this can get called from some tab events)
        if self.graph.scene is not None:
            self.graph.scene.currentChanged(w)

    ## caption type has been changed in widget
    def captionChanged(self, i):
        self.doc.mark()
        if self.graph is not None:
            self.graph.doc.setCaption(i)
            self.graph.performNodes()

    def annotalphaChanged(self):
        self.doc.mark()
        v = self.annotalphaSlider.value()
        self.doc.settings.alpha = v
        if self.graph is not None:
            self.graph.performNodes()

    ## set the caption type (for actual main windows, not macros)
    def setCaption(self, i):
        if self.graph is not None:
            self.graph.doc.setCaption(i)
            self.capCombo.setCurrentIndex(i)

    ## autorun has been changed in widget. This is global,
    # so all windows must agree.
    def autorunChanged(self, i):
        self.doc.mark()
        xform.XFormGraph.autoRun = self.autoRun.isChecked()
        # I'll set autorun on all graphs
        MainUI.updateAutorun()
        # but only rerun this one (turned off because some nodes are REALLY SLOW)

    #        if xform.XFormGraph.autoRun:
    #            self.runAll()

    ## update autorun checkbox states from class variable
    @staticmethod
    def updateAutorun():
        for w in MainUI.windows:
            w.autoRun.setChecked(xform.XFormGraph.autoRun)

    ## open a window showing help for a node type
    def openHelp(self, tp, node=None):
        if tp.helpwin is not None:
            tp.helpwin.close()  # close existing window you may have left open :)
        win = HelpWindow(self, tp=tp, node=node)

    ## add a macro connector, only should be used on macro prototypes   
    def addMacroConnector(self, tp):
        self.doc.mark()
        # create the node inside the prototype
        n = self.graph.create(tp)
        assert (self.isMacro())
        assert (self.macroPrototype is not None)
        n.proto = self.macroPrototype
        # reset the connectors
        n.proto.setConnectors()
        # rebuild the visual components inside the prototype
        self.graph.rebuildGraphics()
        # we also have to rebuild any graphs the macro is in, because
        # the number of connectors will have changed.
        for inst in n.proto.getInstances():
            inst.graph.rebuildGraphics()

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
            self.doc.mark()
            self.macroPrototype.renameType(newname)

    ## perform all in the graph
    def runAll(self, invalidateInputs=True):
        if self.graph is not None:
            # pass in true, indicating we want to ignore autorun. We may not
            # want to invalidate inputs to avoid issue #58.
            self.graph.changed(runAll=True, invalidateInputs=invalidateInputs)
            self.retitleTabs()  # error states may have changed

    def replaceDocumentForUndo(self, d):
        """After an undo/redo, a whole new document may have been deserialised.
        Set this new graph, and make sure the window's tabs point to nodes
        in the new graph rather than the old one."""

        # construct a dict of uid -> node for the new graph
        newGraphDict = {n.name: n for n in d.graph.nodes}

        # replace the graph and document
        self.graph = d.graph
        self.doc = d
        # rebuild the scene without autolayout (coords should be in the data)
        self.graph.constructScene(False)
        self.view.setScene(self.graph.scene)

        for x in self.graph.nodes:
            x.tabs = []

        for title, tab in self.tabs.items():
            # get the new node which replaces the old one if we can. Otherwise
            # delete the tab.
            if tab.node.name in newGraphDict:
                n = newGraphDict[tab.node.name]
                tab.node = n  # replace the node reference in the tab
                n.tabs.append(tab)
            else:
                self.closeTab(tab)

        # we don't want to reload the inputs! (Issue #58)
        self.runAll(invalidateInputs=False)  # refresh everything (yes, slow)

    def showUndoStatus(self):
        import gc

        u, r = self.doc.undoRedoStore.status()
        try:
            from psutil import Process
            process = Process(os.getpid())
            m = process.memory_info().rss
            self.undoStatus.setText("Undo {}, redo {}, {}M".format(u, r, m // (1024 * 1024)))
        except ImportError:
            self.undoStatus.setText("Undo {}, redo {}".format(u, r))
        gc.collect()

        # for x in gc.get_objects():
        #     from ..xform import XForm
        #     if isinstance(x, XForm):
        #         print(str(x))
