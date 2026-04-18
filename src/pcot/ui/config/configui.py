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

from pcot.parameters.taggedaggregates import TaggedDictType, TaggedDict, Maybe, TaggedListType
from pcot.ui.collapser import CollapserSection
from pcot.ui.config.editors import createEditor

MINWIDTH = 700

DUMMY = TaggedDictType(
    aa=("Test string", Maybe(str), "teststringdefault"),
    ab=("Test string 2", Maybe(str), "teststringdefault 2 asdasd asd asd  asd "),
    ac=("Nullable int", Maybe(int), 3),
).setOrdered()

TESTCONFIG = TaggedDictType(
    path=("File path", Maybe(Path), None, "PCOT files (*.pcot *.jpg)"),
    path2=("Any file path", Path, "d:/", None),
    dir=("Dir path", Maybe(Path), None, True),
    btest=("boolean", Maybe(bool), False),
    aa=("Test string", str, "teststringdefault"),
    a=("Test string", str, "teststringdefault"),
    b=("Test string 2", str, "teststringdefault 2 asd asdasd asdasd"),
    nullable=("Nullable int", Maybe(int), 3, (0,200)),
    d =("Choices", Maybe(str), "foo", ("foo", "bar", "baz")),
    e=("Test string", str, "teststringdefault"),
    lst=("List", TaggedListType(Maybe(Path),[Path(f"foo{i}") for i in range(20)],None)),
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


testconfig = TaggedDict(TESTCONFIG)


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
        scrollarea.setMinimumWidth(MINWIDTH+100)
        scrollarea.setMinimumHeight(800)
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


def runConfigUI():
    """This is the function that runs the configuration UI on the main config TaggedDict"""
    import pcot
    dialog = ConfigDialog(pcot.config.data)
    dialog.exec_()  # it's modal
    if dialog.data():
        pcot.ui.log("Setting changes accepted")
        pcot.config.data = dialog.data()
        pcot.config.save()
    else:
        pcot.ui.log("Setting changes rejected")

def test():
    import pcot.config
    app = QtWidgets.QApplication(sys.argv)

    # change this in testing
    if True:
        config = testconfig
    else:
        config = pcot.config.data

    while True:
        import yaml
        dialog = ConfigDialog(config)
        dialog.exec_()
        if dialog.data():
            print("Accepted")
            config = dialog.data()
        s = yaml.dump(config.serialise(forceUnordered=True))
        s = yaml.safe_load(s)
        config = TESTCONFIG.deserialise(s)
        print(json.dumps(config.serialise(forceUnordered=True), indent=2))
        if not dialog.data():
            break

if __name__ == "__main__":
    test()



