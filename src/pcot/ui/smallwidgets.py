# Various little widgets that are too small to go into their own module.
from PyQt5 import QtWidgets


class MouseReleaseSpinBox(QtWidgets.QSpinBox):
    """A version of QSpinBox which sends an editingFinished signal when the mouse button
    is released, rather then just when focus is lost."""

    def __init__(self, parent):
        super().__init__(parent)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.editingFinished.emit()


