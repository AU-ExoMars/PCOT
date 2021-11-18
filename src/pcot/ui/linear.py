from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

from typing import NamedTuple, List


class LinearSetItem(NamedTuple):
    x: float  # position in "timeline" or whatever
    name: str  # name


class LinearSetWidget(QtWidgets.QGraphicsView):
    """This is a widget which deals with linear sets of things in a scrollable view, typically
    timelines."""

    items: List[LinearSetItem]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
