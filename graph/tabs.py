from PyQt5 import QtWidgets,uic
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
    

# A  tab to be loaded. Note that this is a subclass of QWidget,
# not QMainWindow. We subclass this.

class Tab(QtWidgets.QWidget):
    # this safely gets a widget reference
    def getUI(self,type,name):
        x = self.findChild(type,name)
        if x is None:
            raise Exception('cannot find widget '+name)
        return x
    
    def __init__(self,mainui,node,uifile):
        super(Tab,self).__init__()
        self.title=node.name
        self.expanded=None
        self.node=node
        

        # load the UI file
        uic.loadUi(uifile,self)
        # add the widget to the tab, keeping the index at which it was created
        self.idx=mainui.tabWidget.addTab(self,self.title)
        # set the tab's entry in the main UI's dictionary
        mainui.tabs[self.title]=self
        # store a ref to the main UI.
        self.mainui = mainui
        
