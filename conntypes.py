from PyQt5 import QtWidgets, uic, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor,QBrush,QLinearGradient

# Here is where new connection types are registered and tested
# for compatibility: some types may be a "subclass" of others (notably
# the "img" types). I'm aware that this should really be model-only,
# but there's UI stuff in here too because (a) I don't want to separate it out and
# (b) there isn't much more to a type than its name.

brushDict={} # dictionary of name -> brush for connection pad drawing

# creates a gradient consisting of three colours in quick succession
# followed by a wide band of another colour. Used to mark connections such as RGB.

def quickGrad(c1,c2,c3,finalC):
    grad = QLinearGradient(0,0,20,0)
    grad.setColorAt(0,c1)
    grad.setColorAt(0.4,c2)
    grad.setColorAt(0.8,c3)
    grad.setColorAt(1,finalC)
    return grad

brushDict['any']=Qt.red
brushDict['img888']=quickGrad(Qt.red,Qt.green,Qt.blue,QColor(50,50,50))
brushDict['imggrey']=Qt.gray
brushDict['img']=Qt.blue
brushDict['ellipse']=Qt.cyan
brushDict['rect']=Qt.cyan

# convert all brushes to actual QBrush objects
brushDict = { k:QBrush(v) for k,v in brushDict.items()}

# add brushes which are already QBrush down here


# get a brush by name or magenta if no brush is found

def getBrush(typename):
    if typename in brushDict:
        return brushDict[typename]
    else:
        print("Unknown type ",typename)
        return QBrush(Qt.magenta)

# are two connectors compatible?

def isCompatibleConnection(outtype,intype):
    # image inputs accept all images
    if intype == 'img':
        return 'img' in outtype 
    elif intype == 'any': # accepts anything
        return True
    else:
        # otherwise has to match exactly
        return outtype==intype    


