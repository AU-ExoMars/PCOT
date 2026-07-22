from PySide6 import QtWidgets
from PySide6.QtCore import Signal

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
        self.layout = QtWidgets.QVBoxLayout()
        super().setTitle(title)
        self.setLayout(self.layout)
        self.resetOptions(options)

    def resetOptions(self, options):
        self.options = options

        # clear existing buttons
        self.buttons = []
        while self.layout.count() > 0:
            item = self.layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        idx = 0
        for x in options:
            b = QtWidgets.QRadioButton(str(x))
            self.layout.addWidget(b)
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
        self.options = [x.name for x in Datum.types if x.isOKForMacroConnectors]
        super().__init__("Type", self.options, parent)

    def setMode(self, mode=None):
        if mode == 'connector':
            print("Connector mode")
            types = filter(lambda x : x.isOKForMacroConnectors, Datum.types)
        elif mode == 'parameter':
            print("Parameter mode")
            types = filter(lambda x : x.isOKForMacroParameters, Datum.types)
        else:
            types = Datum.types

        types = list(types)
#        print([{"t":x, "p":x.isOKForMacroParameters, "c":x.isOKForMacroConnectors} for x in types])

        type_names = [x.name for x in types]
#        print(type_names)
        self.resetOptions(type_names)

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
