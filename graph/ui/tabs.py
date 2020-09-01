from PyQt5 import QtWidgets,uic,QtCore
from PyQt5.QtCore import Qt
import collections

# the main UI window class. Your application window should inherit from
# this to use dockable tabs.

class DockableTabWindow(QtWidgets.QMainWindow):

    # call this from your subclass after loading the UI file
    def initTabs(self):
        # create the tab widget (assumes a tabWidget exists in the UI)
        self.tabWidget.removeTab(0) # remove the default tabs you can't remove in the designer
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
        self.tabs=collections.OrderedDict()
    
    # initialise this window
    def __init__(self):
        super().__init__() # Call the inherited classes __init__ method

    # close a tab
    def closeTab(self,index):
        tab = self.tabWidget.widget(index)
        tab.node.tab = None
        self.tabWidget.removeTab(index)
        self.tabs = {k:v for k, v in self.tabs.items() if v != tab }
            
    def closeAllTabs(self):
        # first, close all expanded tab windows
        for t in self.tabs.values():
            if t.expanded is not None:
                print("Closing {}".format(t.expanded))
                t.expanded.close()
        # then close all the tabs
        for t in self.tabs.values():
            self.closeTab(self.tabWidget.indexOf(t))
        
        
    # used to undock tab into a window
    def undock(self,i):
        # get the tab contents
        w = self.tabWidget.widget(i)
        # and move them into a new "expanded tab" window
        wnd = ExpandedTab(w,self)

    # reorder all the tabs back to create order, used when a tab is re-docked
    def reorderTabs(self):
        dest = 0 # current tab destination position
        # go through all the tabs in create order
        for t in self.tabs.values():
            if t.expanded is None: # the tab is not expanded
                src = self.tabWidget.indexOf(t) # get current position
                self.tabWidget.tabBar().moveTab(src,dest)
                dest=dest+1    

# a tab which has been expanded into a full window
class ExpandedTab(QtWidgets.QMainWindow):
    def __init__(self,tab,mainui):
        super(ExpandedTab,self).__init__()
        self.tab = tab
        self.setWindowTitle(tab.title)
        self.setCentralWidget(tab)
        tab.show()
        self.resize(tab.size())
        self.show()
        self.mainui=mainui
        # we also create a reference to this window, partly to avoid GC!
        self.tab.expanded=self
        
    def closeEvent(self,event):
        # move window back into tabs
        self.mainui.tabWidget.addTab(self.tab,self.tab.title)
        self.tab.expanded=None
        # and reorder all the tabs
        self.mainui.reorderTabs()
        # but reselect this tab as the front one
        idx = self.mainui.tabWidget.indexOf(self.tab)
        self.mainui.tabWidget.setCurrentIndex(idx)
        event.accept()
        
    # window got focus. Tell the scene.
    def changeEvent(self,event):
        if event.type() == QtCore.QEvent.ActivationChange:
            if self.isActiveWindow():
                self.mainui.scene.currentChanged(self.tab.node)
    

# A tab to be loaded. We subclass this. Once loaded, all ui elements
# are in the 'w' widget

class Tab(QtWidgets.QWidget):
    # the comment field changed, set the data in the node.
    def commentChanged(self):
        self.node.comment = self.comment.toPlainText().strip()
    
    def __init__(self,mainui,node,uifile):
        super(Tab,self).__init__()
        self.title=node.name
        self.expanded=None
        self.node=node

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
        self.comment.setMinimumHeight(20)
        self.comment.setMaximumHeight(150)
        splitter.addWidget(self.comment)
        self.comment.textChanged.connect(self.commentChanged)

        # load the UI file into the main widget
        uic.loadUi(uifile,self.w)
        # add the containing widget (self) to the tabs,
        # keeping the index at which it was created
        self.idx=mainui.tabWidget.addTab(self,self.title)
        # set the tab's entry in the main UI's dictionary
        mainui.tabs[self.title]=self
        # store a ref to the main UI.
        self.mainui = mainui
        
        # resize the splitter based on the existing sizes;
        # have to show the widgets first - sizes() returns
        # zero for invisible widgets
        self.w.show()
        self.comment.show()
        splitter.show()
        self.show()
        total = sum(splitter.sizes())

        splitter.setSizes([total*0.9,total*0.1])
        
    def nodeDeleted(self):
        if self.expanded:
            self.expanded.close()
            self.expanded=None
        idx = self.mainui.tabWidget.indexOf(self)
        self.mainui.tabWidget.removeTab(idx)
        self.node.tab=None

        
    # write this in implementations - updates the tab when the node's data has changed
    def onNodeChanged():
        pass
