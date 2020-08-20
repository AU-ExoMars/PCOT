from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QMessageBox,QTabWidget
from PyQt5.QtGui import QPixmap,QImage
import sys,collections

import tabs
import tab1,tab2,tab3

# the main UI class. As well as its own buttons, it will create some tabs
# inside the tab widget it owns into which it will load sub-uis

class MainUi(QtWidgets.QMainWindow):

    # this safely gets a widget reference
    def getUI(self,type,name):
        x = self.findChild(type,name)
        if x is None:
            raise Exception('cannot find widget'+name)
        return x

    # confirm a quit menu action
    def confirmQuitAction(self):
        reply = QMessageBox.question(self, 
            'Confirm',
            'Really quit?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            app.quit()
            
    # initialise this window
    def __init__(self):
        super(MainUi, self).__init__() # Call the inherited classes __init__ method
        uic.loadUi('main.ui', self) # Load the .main ui 

        # bind actions
        (self.getUI(QtWidgets.QAction,'actionQuit').
            triggered.connect(self.confirmQuitAction))

        # create the tab widget
        self.tabWidget = self.getUI(QTabWidget,'tabWidget')
        self.tabWidget.removeTab(0) # remove the default tabs you can't remove in the designer
        self.tabWidget.removeTab(0)
        
        # set up the double-clicked signal
        self.tabWidget.tabBar().tabBarDoubleClicked.connect(self.undock)

        # store the tabs in an ordered dict, so we can iterate them in create order
        # when we reorder tabs in redocking.                
        self.tabs=collections.OrderedDict()
        # create and load the tabs
        tab1.Tab1(self)
        tab2.Tab2(self)
        # tab 3 takes a title, so we can make multiple copies.
        tab3.Tab3(self,"Tab Three")
        tab3.Tab3(self,"Tab Four")
            
        self.show()

    # used to undock tab into a window
    def undock(self,i):
        # get the tab contents
        w = self.tabWidget.widget(i)
        # and move them into a new "expanded tab" window
        wnd = tabs.ExpandedTab(w,self)

    # reorder all the tabs back to create order, used when a tab is re-docked
    def reorderTabs(self):
        dest = 0 # current tab destination position
        # go through all the tabs in create order
        for t in self.tabs.values():
            if t.expanded is None: # the tab is not expanded
                src = self.tabWidget.indexOf(t) # get current position
                self.tabWidget.tabBar().moveTab(src,dest)
                dest=dest+1    
                changed=True

# Create an instance of QtWidgets.QApplication
app = QtWidgets.QApplication(sys.argv) 
window = MainUi() # Create an instance of our class
app.exec_() # Start the application
