import math
from typing import List

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

import pcot.ui as ui
from pcot import utils

DEFAULTRANGE = 20  # default x range of set view when there are no items

# font for drawing axis text
axesFont = QFont()
axesFont.setFamily('Sans Serif')
axesFont.setPixelSize(10)

# font for drawing item text
markerFont = QFont()
markerFont.setFamily('Sans Serif')
markerFont.setBold(True)
markerFont.setPixelSize(15)


class EntityMarkerItem(QtWidgets.QGraphicsEllipseItem):
    """The selectable marker part of each linear set item"""

    ent: 'LinearSetEntity'

    def __init__(self, x, y, ent, radius=10):
        super().__init__(x - radius / 2, y - radius / 2, radius, radius)
        self.setBrush(Qt.blue)
        self.setPen(Qt.black)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.ent = ent

    def paint(self, painter, option, widget):
        # fake an unselected state so we don't get a border...
        option.state = QtWidgets.QStyle.State_None
        # ...but show the selected state with a colour change #TODO colourblindness!!!
        if self.isSelected():
            self.setBrush(Qt.red)
        else:
            self.setBrush(Qt.blue)
        super().paint(painter, option, widget)


class LinearSetEntity:
    """Something in the linear set"""
    x: float  # position in "timeline" or whatever the horizontal axis is
    name: str  # name
    marker: QtWidgets.QGraphicsItem  # item which can be selected

    def __init__(self, x, name):
        self.x = x
        self.name = name
        self.marker = None

    def createSceneItem(self, scene: 'LinearSetScene', y: float, selected=False):
        """Create some scene items to represent this item, positioned at X,Y in the scene. May be
        created selected, if we're doing a rebuild of a scene with selected items"""
        x = scene.entityToScene(self.x)
        self.marker = EntityMarkerItem(x, y, self, radius=10)
        self.marker.setSelected(selected)
        scene.addItem(self.marker)
        # now the associated text, which isn't selectable
        i = QtWidgets.QGraphicsSimpleTextItem(self.name)
        i.setFont(markerFont)
        utils.text.posAndCentreText(i, x+15, y, centreY=True)
        scene.addItem(i)


class LinearSetScene(QtWidgets.QGraphicsScene):
    """This is a scene for the items in the linear widget - it gets rebuilt often, because I don't
    want to use the view's zoom facility (it would zoom text and icons, not just the space!). The View/Scene transform
    is always fixed to avoid object scaling.

    Entities - things on the line - are owned by the parent widget, and are converted into QGraphics scene items
    in rebuild()"""

    minx: float  # minimum X position
    maxx: float  # maximum X position

    def __init__(self, widget):
        super().__init__(widget.parent)
        self.widget = widget
        self.minx = 0
        self.maxx = 100
        self.selectionChanged.connect(self.onSelChanged)

    def onSelChanged(self):
        pass  # no real need for this to do anything

    def zoom(self, centreX, factor):
        # print(f"Zoom on {centreX} was {self.minx}:{self.maxx}")
        self.minx = centreX - factor * (centreX - self.minx)
        self.maxx = centreX + factor * (self.maxx - centreX)
        # print(f"                  now {self.minx}:{self.maxx}")
        if self.minx < 0:
            self.minx = 0
        self.rebuild()

    def sceneToEntity(self, x):
        """Convert an X-coord in the scene space (i.e. "screen coords") to entity space (e.g. time)"""
        x = x / self.width()
        x *= self.maxx - self.minx
        return x + self.minx

    def entityToScene(self, x):
        """Convert an X-coord in entity space (e.g. time) to scene space (i.e. "screen coords")"""
        x = (x - self.minx) / (self.maxx - self.minx)  # 0-1
        return x * self.width()

    def saveSelection(self):
        """record the selected items during a drag or rebuild"""
        return [i.ent for i in self.selectedItems()]

    def restoreSelection(self, saved):
        """restore a recorded set of selected items"""
        self.clearSelection()
        for ent in saved:
            ent.marker.setSelected(True)

    def createAxes(self):
        """This creates some axis markers - at the moment it's rather dumb"""
        minx = math.ceil(self.minx)
        maxx = math.ceil(self.maxx)
        h = self.height()
        for x in range(minx, maxx):
            xx = self.entityToScene(x)
            i = QtWidgets.QGraphicsLineItem(xx, 0, xx, h)
            i.setPen(QColor(200, 200, 200))
            self.addItem(i)
            i = QtWidgets.QGraphicsSimpleTextItem(str(x))
            i.setFont(axesFont)
            i.setPos(xx, 10)
            self.addItem(i)

    def rebuild(self):
        """Complete rebuild of the scene, done when almost anything happens. Has to remember selected states."""
        ss = self.saveSelection()
        self.clear()
        ui.log(f"range {self.minx, self.maxx}, width {self.width()}")
        self.createAxes()
        for y, i in enumerate(self.widget.items):
            # create item in scene, in scene coordinates (derived from minx,maxx)
            i.createSceneItem(self, self.height() - 10 - (y % 10) * 5)
        self.restoreSelection(ss)


class LinearSetWidget(QtWidgets.QGraphicsView):
    """This is a widget which deals with linear sets of things in a scrollable view, typically
    timelines."""

    scene: LinearSetScene
    items: List[LinearSetEntity]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.parent = parent
        self.prevX = None
        self.scene = LinearSetScene(self)
        self.setScene(self.scene)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)

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
        # print(f"Extent {sc.minx}:{sc.maxx}")
        # print(f"View: {self.width()} Scene: {self.scene.width()}")

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        # set the scene rectangle to the same as the widget
        self.scene.setSceneRect(0, 0, event.size().width(), event.size().height())
        self.scene.rebuild()
        self.update()

    def wheelEvent(self, evt):
        """handle mouse wheel zooming"""
        # Remove possible Anchors
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
        # Get Scene Pos
        target_viewport_pos = self.mapToScene(evt.pos())
        x = target_viewport_pos.x()
        # ZOOM
        if evt.angleDelta().y() < 0:
            factor = 1.1
        else:
            factor = 1 / 1.1
        self.scene.zoom(self.scene.sceneToEntity(x), factor)
        self.setSceneRect(0, 0, self.width(), self.height())
        self.update()

    def mousePressEvent(self, event):
        """Handles the start of a pan. Note that this ONLY calls the superclass event handler
        if we're doing left-button down to start a selection drag. That's so we can use Qt's dragging
        system. We don't do it for other events so that we don't get the rubberbanding and we don't lose
        selections."""

        if event.button() == Qt.RightButton:
            p = self.mapToScene(event.pos())
            x = self.scene.sceneToEntity(p.x())
            self.prevX = x

        if event.button() == Qt.LeftButton:
            # superclass event call to handle selection box drag
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Mouse button release clears the pan state"""
        if self.prevX is not None:
            self.prevX = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Handle panning"""
        if self.prevX is not None:
            p = self.mapToScene(event.pos())
            x = self.scene.sceneToEntity(p.x())
            dx = self.prevX - x
            if self.scene.minx + dx >= 0:
                self.scene.minx += dx
                self.scene.maxx += dx
                self.scene.rebuild()
                self.update()
        super().mouseMoveEvent(event)
