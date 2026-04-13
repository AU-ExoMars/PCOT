"""
Dialog for importing favourites and macros
"""
from PySide2 import QtGui
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QDialog, QDialogButtonBox

from pcot.ui import uiloader


class ImportDialog(QDialog):
    def __init__(self, doc, parent=None):
        super().__init__(parent)
        uiloader.loadUi('import.ui', self)
        self.macstoimport = []
        self.favstoimport = []

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # helper function for checking the box on all items in a model
        def selectAll(model):
            for i in range(model.rowCount()):
                model.item(i).setCheckState(Qt.Checked)

        # buttons for select all
        self.allMacros.clicked.connect(lambda: selectAll(self.macrosList.model()))
        self.allFaves.clicked.connect(lambda: selectAll(self.favesList.model()))

        # create the models the list boxes will use
        self.favmod = QtGui.QStandardItemModel(self.favesList)
        self.macmod = QtGui.QStandardItemModel(self.macrosList)

        # get the document data and add it to the models. Each model item
        # should be checkable.
        for x in doc.favourites.keys():
            item = QtGui.QStandardItem(x)
            item.setCheckable(True)
            self.favmod.appendRow(item)
        self.favesList.setModel(self.favmod)

        for x in doc.macros.keys():
            item = QtGui.QStandardItem(x)
            item.setCheckable(True)
            self.macmod.appendRow(item)
        self.macrosList.setModel(self.macmod)

    def accept(self):
        # get the selected items into lists
        def getlist(mod):
            out = []
            for i in range(mod.rowCount()):
                item = mod.item(i)
                if item.checkState() == Qt.Checked:
                    out.append(item.text())
            return out

        self.macstoimport = getlist(self.macmod)
        self.favstoimport = getlist(self.favmod)

        super().accept()
