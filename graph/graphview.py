from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

class GraphView(QtWidgets.QGraphicsView):
    def __init__(self,parent=None):
        super().__init__(parent)
        
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
