## dictionary of name -> brush for connection pad drawing

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QLinearGradient


from pcot.datum import Datum
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


brushDict[Datum.ANY] = Qt.red
brushDict[Datum.IMGRGB] = quickGrad(Qt.red, Qt.green, Qt.blue, QColor(50, 50, 50))
brushDict[Datum.IMG] = Qt.blue
brushDict[Datum.ELLIPSE] = Qt.cyan
brushDict[Datum.ROI] = Qt.cyan
brushDict[Datum.DATA] = Qt.darkMagenta
brushDict[Datum.NUMBER] = Qt.darkGreen
brushDict[Datum.VARIANT] = QBrush(Qt.black, Qt.DiagCrossPattern)

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
