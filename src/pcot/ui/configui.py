"""
Configuration management UI, using TaggedAggregate values.
"""
import itertools
import sys
from typing import List

from PySide2 import QtWidgets
from PySide2.QtWidgets import QGridLayout, QDialog, QDialogButtonBox, QLineEdit, QVBoxLayout, \
    QGroupBox, QLabel, QScrollArea, QWidget, QSizePolicy

from pcot.parameters.taggedaggregates import TaggedDictType, TaggedDict
from pcot.ui.collapser import CollapserSection

MINWIDTH = 400

DUMMY = TaggedDictType(
    aa=("Test string", str, "teststringdefault"),
    ab=("Test string 2", str, "teststringdefault 2 asdasd asd asd  asd "),
    ac=("Test integer", int, 3),
).setOrdered()

TESTCONFIG = TaggedDictType(
    a=("Test string", str, "teststringdefault"),
    b=("Test string 2", str, "teststringdefault 2 asd asdasd asdasd"),
    c=("Test integer", int, 3),
    subdict1=("subdict",
              TaggedDictType(
                p=("Foo", str, "foo"),
                q=("Bar", str, "bar"),
                zz=("internal", DUMMY, None),
                zz2=("internal", DUMMY, None),
                zz3=("internal", DUMMY, None),
                zz4=("internal", DUMMY, None),
                zz5=("internal", DUMMY, None),
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
        layout=QVBoxLayout(self)        # overall layout containing scroll area and buttonbox

        scrollarea = QScrollArea()
        scrollarea.setFixedHeight(400)
        scrollarea.setMinimumWidth(MINWIDTH+100)
        scrollarea.setWidgetResizable(True)
        layout.addWidget(scrollarea)

        content = QWidget()             # container for items in the scroll area
        scrollarea.setWidget(content)

        contentLayout=QGridLayout()     # layout for items inside the content of the scroll area
        content.setLayout(contentLayout)

        self.layoutDict(contentLayout,[], d)

        # add a stretching row so that things aren't distributed through the box, but gather at the top
        contentLayout.setRowStretch(next(self.ct),1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.adjustSize()
        self.updateGeometry()

    def layoutDict(self, container:QGridLayout, path:List[str], d:TaggedDict):
        """Lays out a TaggedDict in a container, creating subframes for
        sub-dicts. The path is a list of strings giving the path inside the tree
        of dicts, with [] for the root.
        """
        for k,v in d.items():
            desc = d.tag(k).description
            if isinstance(v, TaggedDict):

                # we're adding a sub-dictionary so we need to create a frame,
                # add all the members to that.
                if len(path)==0:
                    # top level, new collapser section
                    group = CollapserSection(desc)
                    group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    layout = QGridLayout()
                    layout.setContentsMargins(20, 0, 0, 0)
                    self.layoutDict(layout, path+[k], v)
                    group.setContentLayout(layout, stretch=True)
                else:
                    # lower levels, we create a group box.
                    group = QGroupBox(desc)
                    group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    group.setMinimumWidth(MINWIDTH)
                    layout = QGridLayout()
                    self.layoutDict(layout, path+[k], v)
                    group.setLayout(layout)
                container.addWidget(group,next(self.ct),0,1,2)
                self.adjustSize()
                self.updateGeometry()
            else:
                # just create label and line editor for simple values
                editor = QLineEdit(str(v))
                row = next(self.ct)
                container.addWidget(QLabel(str(desc)), row, 0, 1, 1)
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

