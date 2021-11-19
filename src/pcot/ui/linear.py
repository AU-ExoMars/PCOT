from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

from typing import NamedTuple, List
import pcot.ui as ui

DEFAULTRANGE = 20       # default x range of set view when there are no items

class LinearSetEntity(NamedTuple):
    """Something in the linear set"""
    x: float        # position in "timeline" or whatever the horizontal axis is
    name: str       # name

    def createSceneItem(self, x: float, y: float):
        """Create a scene item to represent this item, positioned at X,Y in the scene"""
        rad = 10
        r = QtWidgets.QGraphicsEllipseItem(x-rad/2, y-rad/2, rad, rad)
        r.setBrush(Qt.blue)
        r.setPen(Qt.black)
        return r


class LinearSetScene(QtWidgets.QGraphicsScene):
    """This is a scene for the items in the linear widget - it gets rebuilt often, because I don't
    want to use the view's zoom facility (it would zoom text and icons, not just the space!). The View/Scene transform
    is always fixed to avoid object scaling.

    Entities - things on the line - are owned by the parent widget, and are converted into QGraphics scene items
    in rebuild()"""

    minx: float     # minimum X position
    maxx: float     # maximum X position

    def __init__(self, widget):
        self.widget = widget
        self.minx = 0
        self.maxx = 100
        super().__init__(widget.parent)

    def zoom(self, centreX, factor):
        print(f"Zoom on {centreX}")
        self.minx = centreX - factor*(centreX-self.minx)
        self.maxx = centreX + factor*(self.maxx-centreX)
        self.rebuild()

    def sceneToEntity(self, x):
        """Convert an X-coord in the scene space (i.e. "screen coords") to entity space (e.g. time)"""
        x = x/self.width()
        x *= self.maxx-self.minx
        return x+self.minx

    def entityToScene(self, x):
        """Convert an X-coord in entity space (e.g. time) to scene space (i.e. "screen coords")"""
        x = (x-self.minx)/(self.maxx-self.minx)       # 0-1
        return x*self.width()

    def rebuild(self):
        self.clear()
        ui.log(f"range {self.minx,self.maxx}")
        for y, i in enumerate(self.widget.items):
            # create item in scene, in scene coordinates (derived from minx,maxx)
            item = i.createSceneItem(self.entityToScene(i.x), y)
            ui.log(f"pos {i.x},{y}  - X maps to {self.entityToScene(i.x)}")
            # we really only deal with X-coords, but we don't want things to overlap so move them around in Y.
            self.addItem(item)


class LinearSetWidget(QtWidgets.QGraphicsView):
    """This is a widget which deals with linear sets of things in a scrollable view, typically
    timelines."""

    scene: LinearSetScene
    items: List[LinearSetEntity]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.parent = parent
        self._prevMousePos = None
        self.scene = LinearSetScene(self)
        self.setScene(self.scene)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def add(self, x, s):
        self.items.append(LinearSetEntity(x, s))

    def rebuild(self):
        """Rebuild all the scene items; used after zooming/panning/setup/changing/rescaling"""
        self.scene.rebuild()

    def rescale(self):
        """Rescale the minx and maxx values to fit all the items, do after add"""
        sc = self.scene
        vals = [i.x for i in self.items]
        if len(vals):
            sc.minx = min(vals)
            sc.maxx = max(vals)
            if sc.minx >= sc.maxx:
                sc.maxx = sc.minx + DEFAULTRANGE
        else:
            sc.minx = 0
            sc.maxx = DEFAULTRANGE
        print(f"Extent {sc.minx}:{sc.maxx}")
        print(f"View: {self.width()} Scene: {self.scene.width()}")

    ## handle mouse wheel zooming
    def wheelEvent(self, evt):
        # Remove possible Anchors
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
        # Get Scene Pos
        target_viewport_pos = self.mapToScene(evt.pos())
        x = target_viewport_pos.x()
        # ZOOM
        if evt.angleDelta().y() > 0:
            factor = 1.01
        else:
            factor = 1/1.01
        self.scene.zoom(self.scene.sceneToEntity(x), factor)
        self.update()

    ## handle right mouse button panning (when zoomed). This works by
    # looking at the delta from right mouse button events and applying it
    # to the scroll bar.
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._prevMousePos = event.pos()
        else:
            p = self.mapToScene(event.pos())
            x = self.scene.sceneToEntity(p.x())
            print(f"Scene pos={p.x()} entity pos={x}")
            super().mousePressEvent(event)

