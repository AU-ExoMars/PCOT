from PyQt5 import QtWidgets
from PyQt5.QtGui import QColor

import ui

# functions for colour manipulation: converting from (r,g,b) range 0-1 triples to QColor
# and back etc.

# takes a float colour triple, returns the same or None if cancelled

def colDialog(init):
    col = rgb2qcol(init)
    col=QtWidgets.QColorDialog.getColor(col,ui.mainui)
    if col.isValid():
        return qcol2rgb(col)
    else:
        return None
        
def qcol2rgb(qcol):
    r = qcol.red()/255.0
    g = qcol.green()/255.0
    b = qcol.blue()/255.0
    return (r,g,b)
    
def rgb2qcol(rgb):
    r,g,b = rgb
    return QColor(int(r*255),int(g*255),int(b*255))
