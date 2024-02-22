from PySide2 import QtWidgets
from PySide2.QtGui import QColor
import numpy as np

# functions for colour manipulation: converting from (r,g,b) range 0-1 triples to QColor
# and back etc.

# takes a float colour triple, returns the same or None if cancelled

def colDialog(init):
    col = rgb2qcol(init)
    col = QtWidgets.QColorDialog.getColor(col, None)
    if col.isValid():
        return qcol2rgb(col)
    else:
        return None


def qcol2rgb(qcol):
    r = qcol.red() / 255.0
    g = qcol.green() / 255.0
    b = qcol.blue() / 255.0
    return (r, g, b)


def rgb2qcol(rgb, alpha=1.0):
    r, g, b = rgb
    a = np.clip(alpha*256, 0, 255)
    r = np.clip(r*256, 0, 255)
    g = np.clip(g*256, 0, 255)
    b = np.clip(b*256, 0, 255)
    return QColor(int(r), int(g), int(b), int(a))
