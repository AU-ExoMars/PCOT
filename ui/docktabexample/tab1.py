from PyQt5 import QtWidgets
import tabs

# an example tab, which is a subclass of Tab, itself a QWidget. Other than that,
# it works much the same as a main window UI.
class Tab1(tabs.Tab):
    def __init__(self,mainui):
        super(Tab1,self).__init__(mainui,"Tab One","tab1.ui")
        
        self.text = self.getUI(QtWidgets.QPlainTextEdit,"plainTextEdit")
        (self.getUI(QtWidgets.QPushButton,'pushButton').
            clicked.connect(lambda: self.setText("button 1")))
        (self.getUI(QtWidgets.QPushButton,'pushButton_2').
            clicked.connect(lambda: self.setText("button 2")))
        (self.getUI(QtWidgets.QPushButton,'pushButton_3').
            clicked.connect(lambda: self.setText("button 3")))
            
    def setText(self,f):
        self.text.setPlainText(f)

