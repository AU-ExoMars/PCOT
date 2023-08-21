from functools import partial

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QWidget, QGridLayout, QLabel, QCheckBox, QPushButton

from pcot import dq
from pcot.utils import SignalBlocker


class DQWidget(QWidget):
    """Use the bits property as a DQ bitfield"""

    changed = Signal()

    def __init__(self, parent, bits=0):
        super().__init__(parent)
        layout = QGridLayout()
        self.name2widget = dict()
        self.widgets = []

        i = 0
        but = QPushButton("all off")
        but.clicked.connect(self.allOff)
        layout.addWidget(but, 0, i)
        but = QPushButton("all on")
        but.clicked.connect(self.allOn)
        layout.addWidget(but, 1, i)
        i += 1
        for name, mask in dq.DQs.items():
            d = dq.defs[mask]
            label = QLabel(f"{d.name}({d.char})", self)
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label, 0, i, Qt.AlignCenter)
            check = QCheckBox('', self)
            self.name2widget[name] = check
            layout.addWidget(check, 1, i, Qt.AlignCenter)
            check.stateChanged.connect(partial(self.stateChanged, name))
            i += 1

        self.setLayout(layout)
        self.bits = bits
        self.setChecksToBits()

    def setChecksToBits(self):
        for name, mask in dq.DQs.items():
            w = self.name2widget[name]
            w.setChecked(True if ((self.bits & int(mask)) != 0) else False)

    def stateChanged(self, name, val):
        mask = int(dq.DQs[name])
        if val != 0:
            self.bits |= mask
        else:
            self.bits &= ~mask
        self.changed.emit()

    def allOn(self):
        self.bits = dq.MAX
        with SignalBlocker(self):
            self.setChecksToBits()
        self.changed.emit()

    def allOff(self):
        self.bits = 0
        with SignalBlocker(self):
            self.setChecksToBits()
        self.changed.emit()
