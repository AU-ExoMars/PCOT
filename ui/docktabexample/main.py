from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QMessageBox,QTabWidget
import sys

# normally this would be
#   from ui import tabs
# but we're running from inside the module itself in this example

from context import tabs
import tab1,tab2,tab3

class MainUI(tabs.DockableTabWindow):
    # confirm a quit menu action
    def confirmQuitAction(self):
        reply = QMessageBox.question(self, 
            'Confirm',
            'Really quit?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            app.quit()
            
    def __init__(self):
        # generic initialisation
        super(tabs.DockableTabWindow, self).__init__()
        # Load the main user interface, which must have a QTabWidget called
        # 'tabWidget'
        uic.loadUi('main.ui', self) 
        # initialise the tab system (has do be done after the UI has
        # loaded)
        self.initTabs()
        
        # now we can create and load the tabs
        tab1.Tab1(self)
        tab2.Tab2(self)
        # tab 3 takes a title, so we can make multiple copies.
        tab3.Tab3(self,"Tab Three")
        tab3.Tab3(self,"Tab Four")

        # here we can do other UI stuff, such as binding buttons to actions
        (self.getUI(QtWidgets.QAction,'actionQuit').
            triggered.connect(self.confirmQuitAction))

        self.show()
        

        
# Create an instance of QtWidgets.QApplication
app = QtWidgets.QApplication(sys.argv) 
window = MainUI() # Create an instance of our class
app.exec_() # Start the application
