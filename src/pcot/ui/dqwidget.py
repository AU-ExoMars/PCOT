from functools import partial

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QWidget, QGridLayout, QLabel, QCheckBox, QPushButton

from pcot import dq
from pcot.utils import SignalBlocker


class _BaseDQWidget(QWidget):
    """Base DQ bit editing widget. There are two subclasses - one for vertical and one for horizontal
    orientation. They are very brief. Use the bits property as a DQ bitfield"""

    changed = Signal()

    def __init__(self, parent, isVertical, bits):
        super().__init__(parent)
        layout = QGridLayout()
        self.name2widget = dict()
        self.widgets = []

        i = 0   # column or row, depends on orientation.
        but1 = QPushButton("all off")
        but1.clicked.connect(self.allOff)
        but2 = QPushButton("all on")
        but2.clicked.connect(self.allOn)
        if isVertical:
            layout.addWidget(but1, i, 0)
            layout.addWidget(but2, i, 1)
        else:
            layout.addWidget(but1, 0, i)
            layout.addWidget(but2, 1, i)

        i += 1
        for name, mask in dq.DQs.items():
            d = dq.defs[mask]
            label = QLabel(f"{d.name}({d.char})", self)
            check = QCheckBox('', self)
            self.name2widget[name] = check
            check.stateChanged.connect(partial(self.stateChanged, name))

            if isVertical:
                label.setAlignment(Qt.AlignRight)
                layout.addWidget(label, i, 0, Qt.AlignRight)
                layout.addWidget(check, i, 1, Qt.AlignCenter)
            else:
                label.setAlignment(Qt.AlignCenter)
                layout.addWidget(label, 0, i, Qt.AlignCenter)
                layout.addWidget(check, 1, i, Qt.AlignCenter)
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


class DQWidget(_BaseDQWidget):
    """Horizontal DQWidget"""
    def __init__(self, parent, bits=0):
        super().__init__(parent, False, bits)


class DQWidgetVertical(_BaseDQWidget):
    """Vertical DQWidget"""

    def __init__(self, parent, bits=0):
        super().__init__(parent, True, bits)

