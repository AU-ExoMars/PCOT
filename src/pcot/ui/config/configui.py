"""
Configuration management UI, using TaggedAggregate values.
"""
import itertools
import json
import sys
from pathlib import Path
from typing import List

from PySide2 import QtWidgets
from PySide2.QtWidgets import QGridLayout, QDialog, QDialogButtonBox, QVBoxLayout, \
    QGroupBox, QLabel, QScrollArea, QWidget, QSizePolicy

from pcot.parameters.taggedaggregates import TaggedDictType, TaggedDict
from pcot.ui.collapser import CollapserSection
from pcot.ui.config.editors import createEditor

MINWIDTH = 400

DUMMY = TaggedDictType(
    aa=("Test string", str, "teststringdefault"),
    ab=("Test string 2", str, "teststringdefault 2 asdasd asd asd  asd "),
    ac=("Test integer", int, 3),
).setOrdered()

TESTCONFIG = TaggedDictType(
    path=("File path", Path, None, "PCOT files (*.pcot *.jpg)"),
    path2=("Any file path", Path, "d:/", None),
    dir=("Dir path", Path, None, True),
    aa=("Test string", str, "teststringdefault"),
    a=("Test string", str, "teststringdefault"),
    b=("Test string 2", str, "teststringdefault 2 asd asdasd asdasd"),
    c=("Test integer", int, 3, (0,200)),
    d =("Choices", str, "foo", ("foo", "bar", "baz")),
    e=("Test string", str, "teststringdefault"),
    subdict1=("subdict",
              TaggedDictType(
                p=("Foo", str, "foo"),
                q=("Bar", str, "bar", ["bing","bong","bar"]),
                x=("File test", Path, Path()),
                zz=("internal", DUMMY, None),
                zz2=("internal", DUMMY, None),
                zz3=("internal", DUMMY, None),
                zz4=("internal", DUMMY, None),
                zz5=("internal", DUMMY, None),
                r=("Baz", int, 4)).setOrdered(),None)
).setOrdered()


config = TaggedDict(TESTCONFIG)


class ConfigDialog(QDialog):
    """
    Call this with a TaggedDict of data. If accepted, you can use the data() method to get the data out. If not
    accepted this will be None.
    """
    def __init__(self, d, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self.ct = itertools.count()

        self.editors = []

        self.d = d.clone()              # WE OPERATE ON A CLONE!
        self._data = None
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

        self.layoutDict(contentLayout,[], self.d)   # make DAMN SURE we're working on the clone!

        # add a stretching row so that things aren't distributed through the box, but gather at the top
        contentLayout.setRowStretch(next(self.ct),1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.adjustSize()
        self.updateGeometry()

    def data(self):
        return self._data

    def layoutDict(self, container:QGridLayout, path:List[str], d:TaggedDict):
        """Lays out a TaggedDict in a container, creating subframes for
        sub-dicts. The path is a list of strings giving the path inside the tree
        of dicts, with [] for the root.
        """
        for k,v in d.items():
            tag = d.tag(k)
            desc = tag.description
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
                # create the correct kind of editor and add it
                editor = createEditor(self, tag, d, k)
                row = next(self.ct)
                container.addWidget(QLabel(editor.label), row, 0, 1, 1)
                container.addWidget(editor.widget,row,1,1,1)
                self.editors.append((path+[k], editor.widget))

    def accept(self):
        super().accept()
        self._data = self.d


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    dialog = ConfigDialog(config)
    dialog.exec_()
    if dialog.data():
        config = dialog.data()
    print(json.dumps(config.serialise(),indent=4))

