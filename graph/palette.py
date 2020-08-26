from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt
import xformgraph.xform
from xformgraph.xform import XFormType

class PaletteButton(QtWidgets.QPushButton):
    def __init__(self,name):
        super().__init__(name)
        self.name = name

    # drag handling: nabbed from
    # https://stackoverflow.com/questions/57224812/pyqt5-move-button-on-mainwindow-with-drag-drop
    
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
        # set the objectName and click position to keep track of the widget
        # that we're moving and it's click position to ensure that it will
        # be moved accordingly
        stream.writeQString(self.name)
        stream.writeQVariant(self.mousePos)
        # create a custom mimeData format to save the drag info
        mimeData.setData('data/palette', byteArray)
        drag = QtGui.QDrag(self)
        # add a pixmap of the widget to show what's actually moving
        drag.setPixmap(self.grab())
        drag.setMimeData(mimeData)
        # set the hotspot according to the mouse press position
        drag.setHotSpot(self.mousePos - self.rect().topLeft())
        drag.exec_(Qt.MoveAction)    
        
    def click(self):
        pass

# set up the scrolling palette and return a list of the buttons created

def setup(scrollArea,scrollAreaContent):
    # now we set up the palette. I'd just like to say that this was not fun.
    # Not fun at all. It might look straightforward now that I know...
    layout = QtWidgets.QVBoxLayout()
    scrollAreaContent.setLayout(layout)
    buttons=[]
    for k,v in XFormType.all().items():
        b = PaletteButton(k)
        layout.addWidget(b)
        buttons.append(b)

    return buttons
