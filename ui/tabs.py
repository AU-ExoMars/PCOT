## @package ui.tabs
# Dockable tab handling code. Windows which have dockable tabs
# should inherit DockableTabWindow.


from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import Qt
import collections


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
        self.tabWidget.tabBar().tabCloseRequested.connect(self.closeTab)
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
    def closeTab(self, index):
        tab = self.tabWidget.widget(index)
        tab.node.tabs.remove(tab)
        self.tabWidget.removeTab(index)
        self.tabs = {k: v for k, v in self.tabs.items() if v != tab}

    ## close every tab and expanded tab window       
    def closeAllTabs(self):
        # first, close all expanded tab windows
        for t in self.tabs.values():
            if t.expanded is not None:
                print("Closing {}".format(t.expanded))
                t.expanded.close()
        # then close all the tabs
        for t in self.tabs.values():
            self.closeTab(self.tabWidget.indexOf(t))

    ## used to undock tab into a window
    def undock(self, i):
        # get the tab contents
        w = self.tabWidget.widget(i)
        # and move them into a new "expanded tab" window
        wnd = ExpandedTab(w, self)

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
            if self.isActiveWindow():
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
    ## the comment field changed, set the data in the node.
    def commentChanged(self):
        self.node.comment = self.comment.toPlainText().strip()

    ## constructor, which should be called by the subclass ctor
    def __init__(self, window, node, uifile):
        super(Tab, self).__init__()
        self.title = node.displayName
        self.expanded = None
        self.node = node
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
        laylower.setContentsMargins(1,1,1,1)

        widCommentAndEnable = QtWidgets.QWidget()
        layCommentAndEnable = QtWidgets.QHBoxLayout()
        layCommentAndEnable.setContentsMargins(1,1,1,1)
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
        uic.loadUi(uifile, self.w)
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

    ## The tab's widgets have changed the data, we need
    # to perform the node
    # (or all instance nodes of a macro prototype)
    def changed(self):
        self.node.graph.changed(self.node)

    ## enabled has changed  
    def enableChanged(self, b):
        self.node.setEnabled(b)

    ## set node enabled (if the node type has that feature)
    def setNodeEnabled(self, b):
        if self.enable is not None:
            self.enable.setChecked(b)

    ## node has been deleted, remove from tabs
    def nodeDeleted(self):
        if self.expanded:
            self.expanded.close()
            self.expanded = None
        idx = self.window.tabWidget.indexOf(self)
        self.window.tabWidget.removeTab(idx)
        self.node.tabs.remove(self)

    ## force update of tab title and return new title
    def retitle(self):
        self.title = self.node.displayName
        return self.title

    def updateError(self):
        if self.node.error is not None:
            self.errorText.setText("Error "+self.node.error.code+": "+self.node.error.message)
            self.errorText.setVisible(True)
        else:
            self.errorText.setVisible(False)

    ## write this in subclasses - 
    # should update the tab when the node's data has changed
    def onNodeChanged(self):
        pass
