from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QPixmap,QImage

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
    
    def __init__(self,mainui,title,uifile):
        super(Tab,self).__init__()
        self.title=title
        self.expanded=None

        # load the UI file
        uic.loadUi(uifile,self)
        # add the widget to the tab, keeping the index at which it was created
        self.idx=mainui.tabWidget.addTab(self,title)
        # set the tab's entry in the main UI's dictionary
        mainui.tabs[title]=self
        # store a ref to the main UI.
        self.mainui = mainui
        
