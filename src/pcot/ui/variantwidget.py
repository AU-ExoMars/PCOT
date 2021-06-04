from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal

import pcot.conntypes as conntypes


class VariantWidget(QtWidgets.QGroupBox):
    """
    Custom widget for variant type selection in Tabs.
    Signal:
        changed(conntype.Type), emitted when the selection changes
    Method:
        set(conntype.Type) to set the value
    """

    changed = pyqtSignal(conntypes.Type)

    def __init__(self, parent):
        super().__init__(parent)
        # populate with types
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.buttons = []
        idx = 0
        for x in conntypes.types:
            # I would operate on a filtered list, but note that we still need the
            # indices to be incremented on every type.
            if not x.internal:
                b = QtWidgets.QRadioButton(str(x))
                layout.addWidget(b)
                self.buttons.append(b)
                b.idx = idx
                b.toggled.connect(self.buttonToggled)
            idx += 1

    def buttonToggled(self, _):
        for b in self.buttons:
            if b.isChecked():
                t = conntypes.types[b.idx]
                self.changed.emit(t)

    def set(self, t):
        i = conntypes.types.index(t)
        self.buttons[i].setChecked(True)

    def setTitle(self, s):
        super().setTitle(s)
