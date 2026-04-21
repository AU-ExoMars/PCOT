"""
Configuration management UI, using TaggedAggregate values.
"""
import itertools
import json
import sys
from pathlib import Path
from typing import List

from PySide2 import QtWidgets
from PySide2.QtCore import QEvent, Qt
from PySide2.QtWidgets import QGridLayout, QDialog, QDialogButtonBox, QVBoxLayout, \
    QGroupBox, QLabel, QScrollArea, QWidget, QSizePolicy

from pcot.parameters.taggedaggregates import TaggedDictType, TaggedDict, Maybe, TaggedListType
from pcot.ui.collapser import CollapserSection
from pcot.ui.config.editors import createEditor

MINWIDTH = 700
MINHEIGHT = 500

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

class ScrollContent(QWidget):
    """
    A content widget whose sizeHint always reflects its layout,
    and which notifies the scroll area when its size changes.
    """
    def sizeHint(self):
        if self.layout() is not None:
            return self.layout().sizeHint()
        return super().sizeHint()

    def event(self, e):
        if e.type() == QEvent.LayoutRequest:
            self.updateGeometry()
        return super().event(e)



class ConfigWidget(QWidget):
    """
    A reusable widget that lays out a TaggedDict for editing.
    Can be embedded in dialogs or standalone windows.
    """
    def __init__(self, d, parent=None):
        super().__init__(parent)

        self.ct = itertools.count()
        self.editors = []

        self.d = d.clone()      # operate on a clone
        self._data = None

        # Reasonable minimum size for the whole widget (dialog/window size)
        self.setMinimumSize(900, 700)

        layout = QVBoxLayout(self)

        # Scroll area
        scrollarea = QScrollArea()
        scrollarea.setWidgetResizable(True)
        scrollarea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scrollarea.setAlignment(Qt.AlignTop)  # keep content pinned to top
        layout.addWidget(scrollarea)

        # Content inside scroll area
        content = ScrollContent()
        content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        scrollarea.setWidget(content)

        contentLayout = QGridLayout()
        content.setLayout(contentLayout)

        # Populate the layout
        self.layoutDict(contentLayout, [], self.d)

        # Stretch at bottom so items gather at the top *within* the content
        contentLayout.setRowStretch(next(self.ct), 1)

    def data(self):
        return self.d

    def layoutDict(self, container: QGridLayout, path: List[str], d):
        """
        Lays out a TaggedDict in a container, creating subframes for sub-dicts.
        """
        for k, v in d.items():
            tag = d.tag(k)
            desc = tag.description

            if isinstance(v, type(d)):  # TaggedDict
                # Sub-dictionary builds a CollapserSection, or GroupBox at top level
                if len(path) == 0:
                    group = CollapserSection(desc)
                    group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    layout = QGridLayout()
                    layout.setContentsMargins(20, 0, 0, 0)
                    self.layoutDict(layout, path + [k], v)
                    group.setContentLayout(layout, stretch=True)
                else:
                    group = QGroupBox(desc)
                    group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    group.setMinimumWidth(MINWIDTH)
                    layout = QGridLayout()
                    self.layoutDict(layout, path + [k], v)
                    group.setLayout(layout)

                container.addWidget(group, next(self.ct), 0, 1, 2)

            else:
                # Leaf node builds an editor
                editor = createEditor(self, tag, d, k)
                row = next(self.ct)
                container.addWidget(QLabel(editor.label), row, 0)
                container.addWidget(editor.widget, row, 1)
                self.editors.append((path + [k], editor.widget))


class ConfigDialog(QDialog):
    """
    A dialog wrapper around ConfigWidget.
    """
    def __init__(self, d, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")

        layout = QVBoxLayout(self)

        # Embed the widget
        self.widget = ConfigWidget(d, self)
        layout.addWidget(self.widget)

        # OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._data = None

    def accept(self):
        self._data = self.widget.data()
        super().accept()

    def data(self):
        return self._data


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

def runtest():
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
    runtest()



