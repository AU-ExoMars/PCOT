## @package ui.number
# Number widget made up of a dial and text

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

MAXVAL=100

## Number widget made up of a dial and text
class NumberWidget(QtWidgets.QWidget):
    # wire this up to fire when you get a notification of change.
    changed = QtCore.pyqtSignal(float)
    
    ## constructor, generally called automatically from the .ui loader;
    # use init() to set up the widget after creation.
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)

        layout = QtWidgets.QGridLayout()
        layout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        
        self.title = QtWidgets.QLabel()
        self.title.setAlignment(Qt.AlignHCenter|Qt.AlignBottom)
        layout.addWidget(self.title,0,0,1,3)

        self.dial=QtWidgets.QDial()
        self.dial.setMinimumSize(70,70)
        self.dial.setNotchesVisible(True)
        self.dial.setMinimum(0)
        self.dial.setMaximum(MAXVAL)
        layout.addWidget(self.dial,1,0,1,3)
        
        self.mintext = QtWidgets.QLabel("min")
        self.mintext.setAlignment(Qt.AlignHCenter)
        self.mintext.setMinimumSize(0,0)
        layout.addWidget(self.mintext,2,0)
        self.maxtext = QtWidgets.QLabel("max")
        self.maxtext.setAlignment(Qt.AlignHCenter)
        self.maxtext.setMinimumSize(0,0)
        layout.addWidget(self.maxtext,2,2)
        
        
        self.text=QtWidgets.QLineEdit()
        self.text.setValidator(QtGui.QDoubleValidator())
        layout.addWidget(self.text,2,0,3,3)
        
        self.setLayout(layout)
        
        self.init("NOTINIT",0,1,0.5)
        
        self.dial.valueChanged.connect(self.dialChanged)
        self.text.editingFinished.connect(self.textChanged)
        

    ## call from inside a tab constructor to set min,max and initial value
    def init(self,title,mn,mx,v):
        self.title.setText(title)
        self.setRange(mn,mx)
        self.setValue(v)
        
    def _getDial(self):
        v = self.dial.value()/MAXVAL
        return v*(self.mx-self.mn)+self.mn
        
    def _setDial(self,v):
        v = (v-self.mn)/(self.mx-self.mn)
        self.dial.setValue(v*MAXVAL)
    def _setText(self,v):
        self.text.setText("{0:.3g}".format(v))

    ## set widget range        
    def setRange(self,mn,mx):
        self.mn = mn
        self.mx = mx
        self.mintext.setText("{0:.3g}".format(self.mn))
        self.maxtext.setText("{0:.3g}".format(self.mx))
        
    ## set widget value externally
    def setValue(self,v):
        self._setText(v)
        self._setDial(v)
        self.value = v
        self.changed.emit(v)
        
    ## dial changed signal handler
    def dialChanged(self,v):
        self.value = self._getDial()
        self.changed.emit(self.value)
        self._setText(self.value)
        
    ## text change signal handler
    def textChanged(self):
        self.value = float(self.text.text())
        self.changed.emit(self.value)
        self._setDial(self.value)
