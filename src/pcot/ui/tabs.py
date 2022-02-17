"""Dockable tab handling code. Windows which have dockable tabs
should inherit DockableTabWindow.
"""

from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import Qt
import collections

import pcot

## the main UI window class. Your application window should inherit from
# this to use dockable tabs, and have a tabWidget tab container.
from PyQt5.QtGui import QFont


class DockableTabWindow(QtWidgets.QMainWindow):

    ## call this from your subclass after loading the UI file
    def initTabs(self):
        # create the tab widget (assumes a tabWidget exists in the UI)
        self.tabWidget.removeTab(0)  # remove the default tabs you can't remove in the designer
        self.tabWidget.removeTab(0)
        self.tabWidget.setTabsClosable(True)

        # set up the double-clicked signal
        self.tabWidget.tabBar().tabBarDoubleClicked.connect(self.undock)
        # and the close for a tab
        self.tabWidget.tabBar().tabCloseRequested.connect(self.closeTabByIndex)
        # and when we switch tab
        self.tabWidget.currentChanged.connect(self.currentChanged)

        # store the tabs in an ordered dict, so we can iterate them in create order
        # when we reorder tabs in redocking.                
        self.tabs = collections.OrderedDict()

    ## constructor
    def __init__(self):
        super().__init__()  # Call the inherited classes __init__ method
        self.tabs = None

    ## close a tab
    def closeTabByIndex(self, index):
        tab = self.tabWidget.widget(index)
        if tab is not None:
            if tab in tab.node.tabs:
                tab.node.tabs.remove(tab)  # need to check because sometimes an error can mess this up
            self.tabWidget.removeTab(index)
            self.tabs = {k: v for k, v in self.tabs.items() if v != tab}

    def closeTab(self, t):
        if t.expanded:
            t.expanded.close()
        idx = self.tabWidget.indexOf(t)
        if idx >= 0:
            self.closeTabByIndex(idx)

    ## close every tab and expanded tab window
    def closeAllTabs(self):
        # first, close all expanded tab windows
        for t in self.tabs.values():
            if t.expanded is not None:
                t.expanded.close()
        # then close all the tabs
        for t in self.tabs.values():
            self.closeTabByIndex(self.tabWidget.indexOf(t))

    ## used to undock tab into a window
    def undock(self, i):
        # get the tab contents
        tab = self.tabWidget.widget(i)
        # and move them into a new "expanded tab" window
        # Sometimes this seems to get called twice, the second time None is the tab
        # which causes hilarity.
        if tab:
            wnd = ExpandedTab(tab, self)

    ## reorder all the tabs back to create order, used when a tab is re-docked
    def reorderTabs(self):
        dest = 0  # current tab destination position
        # go through all the tabs in create order
        for t in self.tabs.values():
            if t.expanded is None:  # the tab is not expanded
                src = self.tabWidget.indexOf(t)  # get current position
                self.tabWidget.tabBar().moveTab(src, dest)
                dest = dest + 1

                ## remake the entire dictionary with new titles, each of which

    # come from the tab itself
    def retitleTabs(self):
        newdict = collections.OrderedDict()
        for k, v in self.tabs.items():
            newtitle = v.retitle()
            newdict[newtitle] = v
            if v.expanded is not None:
                v.expanded.setWindowTitle(newtitle)
            else:
                idx = self.tabWidget.indexOf(v)
                self.tabWidget.setTabText(idx, newtitle)
        self.tabs = newdict


## a tab which has been expanded into a full window
class ExpandedTab(QtWidgets.QMainWindow):
    def __init__(self, tab, window):
        super(ExpandedTab, self).__init__()
        self.tab = tab
        self.setWindowTitle(tab.title)
        self.setCentralWidget(tab)
        tab.show()
        self.resize(tab.size())
        self.show()
        self.window = window
        # we also create a reference to this window, partly to avoid GC!
        self.tab.expanded = self

    def closeEvent(self, event):
        # move window back into tabs
        self.window.tabWidget.addTab(self.tab, self.tab.title)
        self.tab.expanded = None
        # and reorder all the tabs
        self.window.reorderTabs()
        # but reselect this tab as the front one
        idx = self.window.tabWidget.indexOf(self.tab)
        self.window.tabWidget.setCurrentIndex(idx)
        event.accept()

    ## window got focus. Tell the scene.
    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.ActivationChange:
            if self.isActiveWindow() and self.window.scene():
                self.window.scene().currentChanged(self.tab.node)

    ## retitle window from tab
    def retitle(self):
        self.setWindowTitle(self.tab.title)


tabErrorFont = QFont()
tabErrorFont.setFamily('Sans Serif')
tabErrorFont.setBold(True)
tabErrorFont.setPixelSize(15)


## A tab to be loaded. We subclass this. Once loaded, all ui elements
# are in the 'w' widget
class Tab(QtWidgets.QWidget):

    updatingTabs = False  # we are updating after a perform, don't take too much notice of calls to changed()

    def commentChanged(self):
        """the comment field changed, set the data in the node."""
        self.node.comment = self.comment.toPlainText().strip()

    def __init__(self, window, node, uifile):
        """constructor, which should be called by the subclass ctor"""
        super(Tab, self).__init__()
        self.expanded = None
        self.node = node
        self.retitle()
        # store a ref to the main UI window which created the tab
        self.window = window

        # set the entire tab to be a vertical layout (just there to contain
        # everything, could be any layout)
        lay = QtWidgets.QVBoxLayout()
        self.setLayout(lay)

        # create a splitter inside the tab and add both the main widget
        # and the comment field to it
        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(Qt.Vertical)
        lay.addWidget(splitter)
        self.w = QtWidgets.QWidget()
        splitter.addWidget(self.w)
        self.comment = QtWidgets.QTextEdit()
        self.comment.setPlaceholderText("add a comment on this transformation here")
        self.comment.setMinimumHeight(30)
        self.comment.setMaximumHeight(150)
        widlower = QtWidgets.QWidget()
        splitter.addWidget(widlower)
        laylower = QtWidgets.QVBoxLayout()
        widlower.setLayout(laylower)
        laylower.setContentsMargins(1, 1, 1, 1)

        widCommentAndEnable = QtWidgets.QWidget()
        layCommentAndEnable = QtWidgets.QHBoxLayout()
        layCommentAndEnable.setContentsMargins(1, 1, 1, 1)
        widCommentAndEnable.setLayout(layCommentAndEnable)
        laylower.addWidget(widCommentAndEnable)

        layCommentAndEnable.addWidget(self.comment)
        self.comment.textChanged.connect(self.commentChanged)

        # default invisible error
        self.errorText = QtWidgets.QLabel("")
        self.errorText.setVisible(False)
        self.errorText.setFont(tabErrorFont)
        self.errorText.setStyleSheet("QLabel{color: rgb(200, 0, 0);}")

        laylower.addWidget(self.errorText)

        # most nodes don't have an enabled widget.
        if node.type.hasEnable:
            self.enable = QtWidgets.QRadioButton("enabled")
            layCommentAndEnable.addWidget(self.enable)
            self.enable.setChecked(node.enabled)
            self.enable.toggled.connect(self.enableChanged)
        else:
            self.enable = None

        # load the UI file into the main widget
        x = pcot.config.getAssetAsFile(uifile)
        uic.loadUi(x, self.w)
        # add the containing widget (self) to the tabs,
        # keeping the index at which it was created
        self.idx = window.tabWidget.addTab(self, self.title)
        # set the tab's entry in the main UI's dictionary
        window.tabs[self.title] = self

        # resize the splitter based on the existing sizes;
        # have to show the widgets first - sizes() returns
        # zero for invisible widgets
        self.w.show()
        self.comment.show()
        splitter.show()
        self.show()
        total = sum(splitter.sizes())

        splitter.setSizes([total * 0.9, total * 0.1])

    def changed(self, uiOnly=False):
        """The tab's widgets have changed the data, we need
        to perform the node. (or all instance nodes of a macro prototype).
        If uiOnly is false, just do the uichanged() update, as if autorun were not set.
        We also record an undo mark.

        Note that we don't call this if we're updating tabs in nodeChanged().
        That's because nodeChanged calls onNodeChanged, which can change a lot of widgets,
        each of which will call this method in their valueChanged slot method."""

        if not Tab.updatingTabs:
            self.node.graph.changed(self.node, uiOnly=uiOnly)

    def enableChanged(self, b):
        self.node.setEnabled(b)

    def setNodeEnabled(self, b):
        if self.enable is not None:
            self.enable.setChecked(b)

    def nodeDeleted(self):
        """node has been deleted, remove me from tabs"""
        if self.expanded:
            self.expanded.close()
            self.expanded = None
        idx = self.window.tabWidget.indexOf(self)
        self.window.tabWidget.removeTab(idx)
        self.node.tabs.remove(self)

    def retitle(self):
        """force update of tab title and return new title"""
        t = self.node.displayName
        if self.node.displayName != self.node.type.name:
            t += " ({})".format(self.node.type.name)
        if self.node.rectText is not None:
            t += " [{}]".format(self.node.rectText)
        self.title = t
        return self.title

    def updateError(self):
        """Update the error field"""
        if self.node.error is not None:
            self.errorText.setText("Error " + self.node.error.code + ": " + self.node.error.message)
            self.errorText.setVisible(True)
        else:
            self.errorText.setVisible(False)

    def onNodeChanged(self):
        """should update the tab when the node's data has changed"""
        pass

    def nodeChanged(self):
        """will set a flag to stop undo marking and perform before calling onNodeChanged to update
        tab widgets; this avoids the changes to those widgets triggering another changed and rerun."""
        Tab.updatingTabs = True
        self.onNodeChanged()
        Tab.updatingTabs = False

    def mark(self):
        """the tab is about to change the node! Mark this undo point if we are not updating tabs from the node.
        Yes, we probably shouldn't be calling this at all in the latter case, but it's sometimes hard to avoid."""
        if not Tab.updatingTabs:
            self.node.mark()

    def uichanged(self):
        """The node has changed, but only the user interface needs updating - the outputs will not change."""
        self.node.type.uichange(self.node)    # tell the node to update; for some nodes this calls perform() (e.g. ROIs)
        self.node.updateTabs()

