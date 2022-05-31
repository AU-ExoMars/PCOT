"""A simple dialog for renaming things: use do(oldname)"""

from PySide2 import QtWidgets
from PySide2.QtWidgets import QDialog, QDialogButtonBox


class NameDialog(QDialog):
    ## constructor, takes the old name
    def __init__(self, name):
        super().__init__(None)
        self.setWindowTitle('Rename')
        layout = QtWidgets.QVBoxLayout()
        textwidget = QtWidgets.QWidget()
        textlayout = QtWidgets.QHBoxLayout()
        textwidget.setLayout(textlayout)
        label = QtWidgets.QLabel('New Name:')
        self.edit = QtWidgets.QLineEdit()
        self.edit.setText(name)
        textlayout.addWidget(label)
        textlayout.addWidget(self.edit)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(textwidget)
        layout.addWidget(bb)
        self.setLayout(layout)

    ## once dialog has run, call this to get the name
    def name(self):
        return self.edit.text()


## run the rename dialog, passing the old name and returning a tuple
# of (False,name) or (True,name) - the boolean indicates whether the
# dialog was OKed or Cancelled.

def do(name):
    d = NameDialog(name)
    if d.exec_():
        return True, d.name()
    else:
        return False, name
