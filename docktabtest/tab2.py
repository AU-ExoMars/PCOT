from PyQt5 import QtWidgets
import tabs

# an example tab, which is a subclass of Tab, itself a QWidget. Other than that,
# it works much the same as a main window UI.
class Tab2(tabs.Tab):
    def __init__(self,mainui):
        super(Tab2,self).__init__(mainui,"Tab Two","tab2.ui")
        
        self.rb1 = self.getUI(QtWidgets.QRadioButton,"radioButton")
        self.rb2 = self.getUI(QtWidgets.QRadioButton,"radioButton_2")
        self.dial = self.getUI(QtWidgets.QDial,"dial")
        self.text = self.getUI(QtWidgets.QLabel,"label")
        
        self.rb1.clicked.connect(lambda: self.rb(0))
        self.rb2.clicked.connect(lambda: self.rb(1))
        self.dial.valueChanged.connect(lambda v: self.text.setText(str(v)))
        

        self.rb1.setChecked(True)
        self.text.setText('')
        self.rb(0)
        
    def rb(self,f):
        if f==0:
            c='red'
        else:
            c='blue'
        t = 'background-color: %s;' % c
        self.text.setStyleSheet(t)
