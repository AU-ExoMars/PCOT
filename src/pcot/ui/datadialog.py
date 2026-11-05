from PySide6 import QtWidgets

from pcot.ui.datawidget import DataWidget


class DataDialog(QtWidgets.QDialog):
    def __init__(self, parent, datum):
        super().__init__(parent)
        layout = QtWidgets.QGridLayout()
        self.dw = DataWidget(self,source_section=False, save_button=True)
        layout.addWidget(self.dw)
        self.setLayout(layout)
        self.dw.display(datum)