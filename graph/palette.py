from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt
import xformgraph.xform
from xformgraph.xform import XFormType

view = None

class PaletteButton(QtWidgets.QPushButton):
    def __init__(self,name,view):
        super().__init__(name)
        self.name = name
        self.view = view

    # drag handling: nabbed from
    # https://stackoverflow.com/questions/57224812/pyqt5-move-button-on-mainwindow-with-drag-drop
    # This stuff interacts with the graph view (graphview.py)
    
    def mousePressEvent(self,event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.click()
        elif event.button() == Qt.RightButton:
            self.mousePos = event.pos() # save click position for dragging
            
    def mouseMoveEvent(self,event):
        if event.buttons() != QtCore.Qt.RightButton:
            return
        mimeData = QtCore.QMimeData()
        # create a byte array and a stream that is used to write into
        byteArray = QtCore.QByteArray()
        stream = QtCore.QDataStream(byteArray, QtCore.QIODevice.WriteOnly)
        stream.writeQString(self.name)
        mimeData.setData('data/palette', byteArray)
        drag = QtGui.QDrag(self)
        # add a pixmap of the widget to show what's actually moving
        drag.setPixmap(self.grab())
        drag.setMimeData(mimeData)
        # set the hotspot according to the mouse press position
        drag.setHotSpot(self.mousePos - self.rect().topLeft())
        drag.exec_(Qt.MoveAction)  
        
    def click(self):
        # create a new item at a position decided by the scene
        x = self.view.scene().graph.create(self.name)
        x.xy = self.view.scene().getNewPosition()
        # rebuild the scene
        self.view.scene().rebuild()

# set up the scrolling palette and return a list of the buttons created

def setup(scrollArea,scrollAreaContent,view):
    # now we set up the palette. I'd just like to say that this was not fun.
    # Not fun at all. It might look straightforward now that I know...
    layout = QtWidgets.QVBoxLayout()
    scrollAreaContent.setLayout(layout)
    buttons=[]
    for k,v in XFormType.all().items():
        b = PaletteButton(k,view)
        layout.addWidget(b)
        buttons.append(b)

    return buttons
