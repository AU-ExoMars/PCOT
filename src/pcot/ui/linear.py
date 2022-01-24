from typing import List, Any, Set, Callable

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

import numpy as np
import pcot.ui as ui
from pcot import utils

DEFAULTRANGE = 20  # default x range of set view when there are no items

# font for drawing item text
markerFont = QFont()
markerFont.setFamily('Sans Serif')
# markerFont.setBold(True)
markerFont.setPixelSize(12)


def entityMarkerInitSetup(obj, ent):
    """Setups up some common stuff in item initialisation - the problem is that the base class of all these items
    is a QGraphicsItem, but we want common stuff to happen. We could do this with mixins and careful use of the MRO,
    but this is easier to understand (I think)."""
    obj.setBrush(Qt.blue)
    obj.setPen(Qt.black)
    obj.selCol = Qt.red
    obj.unselCol = Qt.blue
    obj.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
    obj.ent = ent


def entityMarkerPaintSetup(obj, option, unselCol, selCol):
    """Used to set up some common stuff for drawing items. We could potentially do this as a decorator,
    really - the decorator would provide paint(), wrapping a call to super.paint with code that does this."""
    # fake an unselected state so we don't get a border...
    option.state = QtWidgets.QStyle.State_None
    # ...but show the selected state with a colour change #TODO colourblindness!!!
    if obj.isSelected():
        obj.setBrush(selCol)
    else:
        obj.setBrush(unselCol)


class EntityMarkerItem(QtWidgets.QGraphicsEllipseItem):
    """The selectable marker part of each linear set item"""

    ent: 'LinearSetEntity'

    def __init__(self, x, y, ent, radius=10):
        super().__init__(x - radius / 2, y - radius / 2, radius, radius)
        entityMarkerInitSetup(self, ent)

    def paint(self, painter, option, widget):
        """and draw."""
        entityMarkerPaintSetup(self, option, self.unselCol, self.selCol)
        super().paint(painter, option, widget)


class LinearSetEntity:
    """Something in the linear set"""
    x: float  # position in "timeline" or whatever the horizontal axis is
    yOffset: int  # an integer Y-offset used to differentiate different object types
    text: str  # name
    marker: QtWidgets.QGraphicsItem  # item which can be selected
    data: Any  # the underlying data object

    def __init__(self, x, yOffset, text, data):
        self.x = x
        self.yOffset = yOffset
        self.text = text
        self.marker = None
        self.data = data

    def createMarkerItem(self, x, y):
        """Create the actual marker item - called from createSceneItem, this can be overriden to provide
        a different looking marker"""
        return EntityMarkerItem(x, y, self)

    def createSceneItem(self, scene: 'LinearSetScene', selected=False):
        """Create some scene items to represent this item, positioned at X in the scene.
        The Y position is calculated from yOffset. May be created selected, if we're doing a
        rebuild of a scene with selected items"""
        x = scene.entityToScene(self.x)
        y = self.yOffset * 15 + 30 + scene.itemYOffset  # a bit ad-hoc...
        self.marker = self.createMarkerItem(x, y)
        self.marker.setSelected(selected)
        scene.addItem(self.marker)
        # now the associated text, which isn't selectable
        i = QtWidgets.QGraphicsSimpleTextItem(self.text)
        i.setFont(markerFont)
        utils.text.posAndCentreText(i, x + 15, y, centreY=True)
        scene.addItem(i)


class TickRenderer:
    """A definition for a set of ticks on the X-axis - how to render them, when they should
    appear and how far apart they are. We avoid placing ticks if there are existing ticks."""

    spacing: float  # how far apart the ticks are
    minxdist: float  # if the ticks are closer together than this number of pixels, don't draw
    maxxdist: float # if the ticks are further apart or equal to than this no. of pixels, don't draw - ignored if None
    font: QFont  # font to use (or None if no text)
    textoffset: float  # if there is a font, the y offset
    textgenfunc: Callable[[float], str]  # functor to generate text (default is rounded to 1 sig fig)
    linecol: QColor  # colour of axis line
    textcol: QColor  # colour of text
    linelen: float  # length of tick line as fraction of widget height
    textalways: bool  # true if the 'tick overwrite' thing ignores text, so text is always printed even if the tick isn't.

    def __init__(self, spacing, fontsize=10, minxdist=10, maxxdist=None, textoffset=0, textgenfunc=None, linecol=(200, 200, 200),
                 linelen=1.0, textcol=(0, 0, 0), textalways=False):
        self.spacing = float(spacing)
        self.minxdist = float(minxdist)
        self.maxxdist = float(maxxdist) if maxxdist is not None else None
        self.textoffset = textoffset
        self.textgenfunc = textgenfunc
        self.linelen = linelen
        self.linecol = QColor(*linecol)
        self.textcol = QColor(*textcol)
        self.textalways = textalways
        if fontsize > 0:
            self.font = QFont()
            self.font.setFamily('Sans Serif')
            self.font.setPixelSize(fontsize)
        else:
            self.font = None

    def generate(self, scene):
        """Add the ticks to the scene"""
        # first check X distance between ticks
        xdist = scene.entityToScene(self.spacing) - scene.entityToScene(0)
        if xdist < self.minxdist or self.maxxdist is not None and xdist >= self.maxxdist:
            return

        # now get the positions of first and last tick we will build
        start = scene.minx - (scene.minx % self.spacing)  # x of start rounded down to nearest 'spacing'
        end = scene.maxx - (scene.maxx % self.spacing) + self.spacing  # x of end rounded up similarly

        h = scene.height()
        # go through all tick positions.
        for x in np.arange(start, end, self.spacing):
            xx = scene.entityToScene(x)
            if not scene.hasTickAlready(xx):
                # only do something if there isn't a tick there
                # create the line
                i = QtWidgets.QGraphicsLineItem(xx, 0, xx, h * self.linelen)
                i.setPen(self.linecol)
                scene.addItem(i)
            if not scene.hasTickAlready(xx) or self.textalways:
                scene.markTick(xx)  # NOW mark the tick.
                # that was the same check again for the text, but this time we take textalways into account
                # now if there is text, create that, using the text generation function
                # if there is one - otherwise just a number to 1 sig digit.
                if self.font:
                    if self.textgenfunc:
                        txt = self.textgenfunc(x)
                    else:
                        txt = f"{x:.1f}"
                    i = QtWidgets.QGraphicsSimpleTextItem(txt)
                    i.setBrush(self.textcol)
                    i.setFont(self.font)
                    i.setPos(xx, 10 + self.textoffset)
                    i.setZValue(1)  # text always on top
                    scene.addItem(i)


class LinearSetScene(QtWidgets.QGraphicsScene):
    """This is a scene for the items in the linear widget - it gets rebuilt often, because I don't
    want to use the view's zoom facility (it would zoom text and icons, not just the space!). The View/Scene transform
    is always fixed to avoid object scaling.

    Entities - things on the line - are owned by the parent widget, and are converted into QGraphics scene items
    in rebuild()"""

    minx: float  # minimum X position
    maxx: float  # maximum X position
    tickRenderers: List[TickRenderer]  # x-axis ticks to create (or not)
    ticksAlreadyPlaced: Set[float]  # stores ticks already placed in this rebuild
    itemYOffset: float  # y offset added to all items

    def __init__(self, widget):
        super().__init__(widget.parent)
        self.widget = widget
        self.minx = 0
        self.maxx = 100
        self.selectionChanged.connect(self.onSelChanged)
        self.itemYOffset = 0
        self.tickRenderers = []

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

    def createTicks(self):
        """create scene items for axes in order of how they were added"""
        self.ticksAlreadyPlaced = set()
        for a in self.tickRenderers:
            a.generate(self)

    def hasTickAlready(self, x):
        """used to check if a tick has already been placed"""
        return int(x) in self.ticksAlreadyPlaced

    def markTick(self, x):
        """used to mark that a tick has already been placed"""
        self.ticksAlreadyPlaced.add(int(x))

    def rebuild(self):
        """Complete rebuild of the scene, done when almost anything happens. Has to remember selected states."""
        ss = self.saveSelection()
        self.clear()
        ui.log(f"range {self.minx, self.maxx}, width {self.width()}")
        self.createTicks()
        for i in self.widget.items:
            # create item in scene, in scene coordinates (derived from minx,maxx)
            i.createSceneItem(self)
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

    def setYOffset(self, y):
        """change the offset added to all items, generally to make room for axis text at the top"""
        self.scene.itemYOffset = y

    def addTickRenderer(self, axis: TickRenderer):
        """add an tick-renderer to the widget. If an renderer would place a new tick over an old one, the
        new tick will be ignored, so the order of addition is significant (i.e. add 'bigger' ticks first)"""
        self.scene.tickRenderers.append(axis)

    def setItems(self, items: List[LinearSetEntity]):
        """Set the items we are going to render"""
        self.items = items

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
