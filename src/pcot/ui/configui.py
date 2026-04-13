"""
Configuration management UI, using TaggedAggregate values.
"""
import sys
import itertools
from typing import List

from PySide2 import QtWidgets
from PySide2.QtWidgets import QGridLayout, QDialog, QFormLayout, QDialogButtonBox, QLineEdit, QVBoxLayout, \
    QFrame, QGroupBox, QLabel

from pcot.parameters.taggedaggregates import TaggedDictType, TaggedDict

TESTCONFIG = TaggedDictType(
    a=("Test string", str, "teststringdefault"),
    b=("Test string 2", str, "teststringdefault 2"),
    c=("Test integer", int, 3),
    subdict1=("subdict",
              TaggedDictType(
                p=("Foo", str, "foo"),
                q=("Bar", str, "bar"),
                r=("Baz", int, 4)).setOrdered(),None)
).setOrdered()

config = TaggedDict(TESTCONFIG)


class ConfigDialog(QDialog):
    def __init__(self, d, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self.ct = itertools.count()

        self.editors = []

        self.d = d
        layout=QVBoxLayout(self)
        self.form=QGridLayout()
        layout.addLayout(self.form)

        self.layoutDict(self.form,[], d)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def layoutDict(self, container:QGridLayout, path:List[str], d:TaggedDict):
        """Lays out a TaggedDict in a container, creating subframes for
        sub-dicts. The path is a list of strings giving the path inside the tree
        of dicts, with [] for the root.
        """
        for k,v in d.items():
            if isinstance(v, TaggedDict):
                # we're adding a sub-dictionary so we need to create a frame,
                # add all the members to that.
                group = QGroupBox(k)
                layout = QGridLayout(group)
                group.setLayout(layout)

                container.addWidget(group,next(self.ct),0,1,2)
                self.layoutDict(layout, path+[k], v)
            else:
                # just create label and line editor for simple values
                editor = QLineEdit(str(v))
                row = next(self.ct)
                container.addWidget(QLabel(str(k)), row, 0, 1, 1)
                container.addWidget(editor,row,1,1,1)
                self.editors.append((path+[k], editor))

    def accept(self):
        print("Accepted")
        # just dump the editor paths for now.
        for editor in self.editors:
            path, e = editor
            print(path)
        super().accept()



def run():
    dialog = ConfigDialog(config)
    dialog.exec_()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    dialog = ConfigDialog(config)
    dialog.exec_()

