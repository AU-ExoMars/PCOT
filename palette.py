from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt
from xform import XFormType

view = None

groups = ["source","macros","maths","processing","calibration","data","colour","regions","utility"]

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


class Palette:
    # set up the scrolling palette as part of view initialisation, will populate
    # with initial data
    def __init__(self,scrollArea,scrollAreaContent,view):
        layout = QtWidgets.QVBoxLayout()
        scrollAreaContent.setLayout(layout)
        scrollArea.setMinimumWidth(150)
        self.scrollAreaContent=scrollAreaContent
        self.view = view
        self.layout = layout
        self.populate()

    def populate(self):    
        grouplists = {x:[] for x in groups}
        # we want the keys in sorted order
        all = XFormType.all()
        ks = sorted(all.keys())
        # add xformtypes to a list for each group
        for k in ks:
            v = all[k]
            if not v.group in groups:
                # "hidden" is a special group which doesn't appear in the palette, used for 
                # things like macro connectors.
                if v.group != 'hidden':
                    raise Exception("node '{}' not in any group defined in palette.py!".format(k))
            else:
                grouplists[v.group].append(k)
    
        # clear previous buttons and seps - we do this by going
        # backwards (so we keep the indices the same) and setting
        # each item's parent to none. Ugh.
        for i in reversed(range(self.layout.count())): 
            self.layout.itemAt(i).widget().setParent(None)        

        # add buttons and separators for each group
        for g in groups:
            sep = QtWidgets.QLabel(g)
            sep.setStyleSheet("background-color:rgb(200,200,200)")
            self.layout.addWidget(sep)
            for k in grouplists[g]:
                v = all[k]
                b = PaletteButton(k,self.view)
                if g=='macros':
                    b.setStyleSheet("background-color:rgb(220,220,140)")
                self.layout.addWidget(b)
            
