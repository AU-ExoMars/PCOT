from PySide2 import QtWidgets
from PySide2.QtCore import Signal

from pcot.datum import Datum
from pcot import datumtypes

import logging
logger = logging.getLogger(__name__)


class VariantWidget(QtWidgets.QGroupBox):
    """
    Custom widget for box containing multiple radio buttons, vertically arranged. To use it,
    subclass it and pass the list of strings into the constructor.
    Signal:
        changed(int), emitted when the selection changes, with the index of the selected item.
    Methods:
        set(int) to set the value
    """

    changed = Signal(datumtypes.Type)

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


class DatumTypeWidget(VariantWidget):

    # unlike the generic version, this emits a Datum type object.
    changed = Signal(datumtypes.Type)

    def __init__(self, parent):
        self.options = [x.name for x in Datum.types]
        super().__init__("Type", self.options, parent)

    def set(self, t):
        """This version takes a DatumType"""
        i = self.options.index(t.name)
        self.buttons[i].setChecked(True)

    def buttonToggled(self, checked):
        if checked:     # ignore button toggling off event
            for b in self.buttons:
                if b.isChecked():
                    name = self.options[b.idx]
                    obj = datumtypes.typesByName[name]
                    self.changed.emit(obj)
