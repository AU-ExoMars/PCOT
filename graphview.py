from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

class GraphView(QtWidgets.QGraphicsView):
    def __init__(self,parent=None):
        super().__init__(parent)
        
    def setWindow(self,win,macroWindow):
        self.window = win
        if macroWindow:
            self.setStyleSheet("background-color:rgb(255,255,220)")
        
        
    # handle mouse wheel zooming
    
    def wheelEvent(self, evt):
        #Remove possible Anchors
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
        #Get Scene Pos
        target_viewport_pos = self.mapToScene(evt.pos())
        #Translate Scene
        self.translate(target_viewport_pos.x(),target_viewport_pos.y())
        # ZOOM
        if evt.angleDelta().y() > 0:
            factor = 1.2
        else:
            factor = 0.8333
        self.scale(factor,factor)
            
        # Translate back
        self.translate(-target_viewport_pos.x(),-target_viewport_pos.y())

    # handle right mouse button panning (when zoomed) - this works by
    # looking at the delta from right mouse button events and applying it
    # to the scroll bar.
    
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.__prevMousePos = event.pos()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.RightButton: 
            offset = self.__prevMousePos - event.pos()
            self.__prevMousePos = event.pos()

            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + offset.y())
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + offset.x())
        else:
            super().mouseMoveEvent(event)
            
    # events for handling reception of dragged palette buttons - this
    # interacts with the palette buttons in palette.py

    def dragMoveEvent(self, e):
        e.accept()

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat('data/palette'):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        bs = e.mimeData().data('data/palette')
        # open the data stream and read the name
        stream = QtCore.QDataStream(bs)
        name = stream.readQString()
        # now we need to make one of those and add it to the graph!
        x = self.scene().graph.create(name)
        # we have to fudge up a position for this; normally grandalf
        # creates these. No need to set width and height.
        pos = self.mapToScene(e.pos())
        x.xy = (pos.x(),pos.y())
        # and build the scene with the new objects
        self.scene().rebuild()
        
                
