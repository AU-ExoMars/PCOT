from PyQt5 import QtWidgets,uic,QtCore
from PyQt5.QtCore import Qt
import collections

# the main UI window class. Your application window should inherit from
# this to use dockable tabs.

class DockableTabWindow(QtWidgets.QMainWindow):

    # this safely gets a widget reference
    def getUI(self,type,name):
        x = self.findChild(type,name)
        if x is None:
            raise Exception('cannot find widget'+name)
        return x

    # call this from your subclass after loading the UI file
    def initTabs(self):
        # create the tab widget
        self.tabWidget = self.getUI(QtWidgets.QTabWidget,'tabWidget')
        self.tabWidget.removeTab(0) # remove the default tabs you can't remove in the designer
        self.tabWidget.removeTab(0)
        self.tabWidget.setTabsClosable(True)
        
        # set up the double-clicked signal
        self.tabWidget.tabBar().tabBarDoubleClicked.connect(self.undock)
        # and the close for a tab
        self.tabWidget.tabBar().tabCloseRequested.connect(self.closeTab)

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
    

# A  tab to be loaded. We subclass this.

class Tab(QtWidgets.QWidget):
    # this safely gets a widget reference
    def getUI(self,type,name):
        x = self.findChild(type,name)
        if x is None:
            raise Exception('cannot find widget '+name)
        return x
        
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
        mainwidg = QtWidgets.QWidget()
        splitter.addWidget(mainwidg)
        self.comment = QtWidgets.QTextEdit()
        self.comment.setPlaceholderText("add a comment on this transformation here")
        self.comment.setMinimumHeight(20)
        self.comment.setMaximumHeight(150)
        splitter.addWidget(self.comment)
        self.comment.textChanged.connect(self.commentChanged)

        # load the UI file into the main widget
        uic.loadUi(uifile,mainwidg)
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
        mainwidg.show()
        self.comment.show()
        splitter.show()
        self.show()
        total = sum(splitter.sizes())

        splitter.setSizes([total*0.9,total*0.1])
        
    # write this in implementations - updates the tab when the node's data has changed
    def onNodeChanged():
        pass
