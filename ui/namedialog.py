from PyQt5 import QtWidgets, uic, QtGui, QtCore
from PyQt5.QtWidgets import QDialog,QDialogButtonBox

class NameDialog(QDialog):
    def __init__(self,name):
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
    def name(self):
        return self.edit.text()
        
def do(name):
    d = NameDialog(name)
    if d.exec_():
        return True,d.name()
    else:
        return False,name
