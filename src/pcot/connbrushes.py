## dictionary of name -> brush for connection pad drawing

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QLinearGradient


from pcot.conntypes import *
brushDict = {}


## creates a gradient consisting of three colours in quick succession
# followed by a wide band of another colour. Used to mark connections such as RGB.

def quickGrad(c1, c2, c3, finalC):
    grad = QLinearGradient(0, 0, 20, 0)
    grad.setColorAt(0, c1)
    grad.setColorAt(0.4, c2)
    grad.setColorAt(0.8, c3)
    grad.setColorAt(1, finalC)
    return grad


brushDict[ANY] = Qt.red
brushDict[IMGRGB] = quickGrad(Qt.red, Qt.green, Qt.blue, QColor(50, 50, 50))
brushDict[IMGGREY] = Qt.gray
brushDict[IMG] = Qt.blue
brushDict[ELLIPSE] = Qt.cyan
brushDict[RECT] = Qt.cyan
brushDict[DATA] = Qt.darkMagenta
brushDict[NUMBER] = Qt.darkGreen
brushDict[VARIANT] = QBrush(Qt.black, Qt.DiagCrossPattern)

## complete list of all types
types = [x for x in brushDict]

# convert all brushes to actual QBrush objects
brushDict = {k: QBrush(v) for k, v in brushDict.items()}


# add brushes which are already QBrush down here

## get a brush by name or magenta if no brush is found
def getBrush(typename):
    if typename in brushDict:
        return brushDict[typename]
    else:
        print("Unknown type ", typename)
        return QBrush(Qt.magenta)
