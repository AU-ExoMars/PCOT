import os
import re
from typing import TYPE_CHECKING, List

from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtWidgets import QFileSystemModel

import pcot.ui
from pcot.channelsource import FileChannelSource
from pcot.pancamimage import ImageCube

if TYPE_CHECKING:
    from inputs.inp import Input, InputMethod


class MethodSelectButton(QtWidgets.QPushButton):
    def __init__(self, inp, m):
        super().__init__()
        self.input = inp
        self.method = m
        self.setText(m.getName())
        self.clicked.connect(self.onClick)

    def onClick(self):
        self.input.selectMethod(self.method)


class InputWindow(QtWidgets.QMainWindow):
    input: 'Input'
    widgets: List['MethodWidget']

    def __init__(self, inp: 'Input'):
        super().__init__()
        self.input = inp
        self.widgets = []

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        # top box contains the buttons determining what sort of input this is
        layout = QtWidgets.QVBoxLayout()
        central.setLayout(layout)

        topBox = QtWidgets.QWidget()
        topBoxLayout = QtWidgets.QHBoxLayout()
        topBox.setLayout(topBoxLayout)
        layout.addWidget(topBox)
        topBox.setMaximumHeight(50)

        for m in self.input.methods:
            b = MethodSelectButton(self.input, m)
            topBoxLayout.addWidget(b)
            widget = m.createWidget()
            self.widgets.append(widget)
            layout.addWidget(widget)

            if not m.isActive():
                widget.setVisible(False)

        self.show()

    def closeEvent(self, event):
        print("Closing input window")
        self.input.onWindowClosed()
        event.accept()

    def methodChanged(self):
        for w in self.widgets:
            w.setVisible(w.method.isActive())


# Widgets for viewing/controlling the Methods (i.e. input types within the Input)

class MethodWidget(QtWidgets.QWidget):
    method: 'InputMethod'

    def __init__(self, m):
        self.method = m
        super().__init__()


class NullMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QtWidgets.QLabel("NULL INPUT"))


class PlaceholderMethodWidget(MethodWidget):
    def __init__(self, m):
        super().__init__(m)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        text = m.getName() + " PLACEHOLDER"
        layout.addWidget(QtWidgets.QLabel(text))
