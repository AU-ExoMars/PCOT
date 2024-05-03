from PySide2 import QtWidgets
from PySide2.QtCore import Signal

from pcot import datum
from pcot.datum import Datum


class VariantWidget(QtWidgets.QGroupBox):
    """
    Custom widget for box containing multiple radio buttons, vertically arranged. To use it,
    subclass it and pass the list of strings into the constructor.
    Signal:
        changed(int), emitted when the selection changes, with the index of the selected item.
    Methods:
        set(int) to set the value
    """

    changed = Signal(int)

    def __init__(self, title, options, parent):
        super().__init__(parent)
        # populate with types
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.buttons = []
        idx = 0
        self.options = options
        super().setTitle(title)
        for x in options:
            b = QtWidgets.QRadioButton(str(x))
            layout.addWidget(b)
            self.buttons.append(b)
            b.idx = idx
            b.toggled.connect(self.buttonToggled)
            idx += 1

    def buttonToggled(self, checked):
        if checked:     # ignore button toggling off event
            for b in self.buttons:
                if b.isChecked():
                    self.changed.emit(b.idx)

    def set(self, i):
        self.buttons[i].setChecked(True)

