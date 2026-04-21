"""
Configuration management UI, using TaggedAggregate values.
"""
import json
import sys
from pathlib import Path

from PySide2 import QtWidgets
from PySide2.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox

from pcot.parameters.taggedaggregates import TaggedDictType, Maybe, TaggedListType, TaggedDict
from pcot.ui.taggedaggregates import ConfigWidget


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



