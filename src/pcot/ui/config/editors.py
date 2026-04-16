"""
Editors for the config UI. These are widgets and tools to allow them to modify TaggedAggregate data.
"""
from pathlib import Path
from typing import Tuple, Optional

from PySide2 import QtWidgets

from pcot.parameters.taggedaggregates import Tag, TaggedList, TaggedDict, Maybe
from pcot.ui.filepathedit import FilePathEdit


class Editor:
    def __init__(self, tag:Tag, aggregate:TaggedList|TaggedDict, key_or_index: int|str):
        """
        container - the thing containing what is to be edited; a TaggedList or a TaggedDict.
        key_or_index - for a TD, it's the key; for a TL, it's the index.
        """
        self.aggregate = aggregate
        self.agg_type = aggregate._type
        self.key_or_index = key_or_index
        self.label=tag.description
        self.widget = None


class TextEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str):
        super().__init__(tag, container, key_or_index)
        self.widget = QtWidgets.QLineEdit()
        self.widget.setText(container[key_or_index])
        # can't connect to the method directly, because the class is not a QObject
        self.widget.textChanged.connect(lambda t: self.changed(t))

    def changed(self, t):
        print(f"Setting {self.aggregate}[{self.key_or_index}] to {t}")
        self.aggregate[self.key_or_index] = t


class IntEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str, range:Optional[Tuple[int,int]]):
        super().__init__(tag, container, key_or_index)
        self.widget = QtWidgets.QSpinBox()
        if not range:
            range = (0,99)  # this is the default range for a qspinbox, but we set it explicitly anyway
        self.label = f"{self.label} ({range[0]}..{range[1]})"
        self.widget.setRange(*range)
        self.widget.setValue(container[key_or_index])
        self.widget.valueChanged.connect(lambda v: self.changed(v))

    def changed(self, v):
        self.aggregate[self.key_or_index] = v


class ComboEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str):
        super().__init__(tag, container, key_or_index)
        self.widget = QtWidgets.QComboBox()
        for x in tag.valid_choices:
            self.widget.addItem(x)
        self.widget.setCurrentText(container[key_or_index])
        # can't connect to the method directly, because the class is not a QObject
        self.widget.currentTextChanged.connect(lambda t: self.changed(t))

    def changed(self, t):
        self.aggregate[self.key_or_index] = t


class PathEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str):
        super().__init__(tag, container, key_or_index)

        if isinstance(tag.valid_choices, str):
            filt = tag.valid_choices
            is_dir = False
        else:
            filt = ""
            is_dir = bool(tag.valid_choices)

        self.widget = FilePathEdit(mode=FilePathEdit.DIRECTORY if is_dir else FilePathEdit.FILE, filter=filt)
        self.widget.setPath(str(container[key_or_index]))
        self.widget.pathChanged.connect(lambda t: self.changed(t))

    def changed(self, t):
        self.aggregate[self.key_or_index] = t


class BoolEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str):
        super().__init__(tag, container, key_or_index)
        self.widget = QtWidgets.QCheckBox("")
        self.widget.setChecked(container[key_or_index])
        # can't connect to the method directly, because the class is not a QObject
        self.widget.stateChanged.connect(lambda t: self.changed(t))

    def changed(self, _):
        print(f"Setting {self.aggregate}[{self.key_or_index}] to {self.widget.isChecked()}")
        self.aggregate[self.key_or_index] = self.widget.isChecked()


def createEditor(parent, tag: Tag, aggregate:TaggedList|TaggedDict, key_or_index:int|str):
    tp = tag.type
    if isinstance(tp, Maybe):
        tp = tp.type_if_exists

    if tp == str:
        if tag.valid_choices:
            return ComboEditor(tag, aggregate, key_or_index)
        else:
            return TextEditor(tag, aggregate, key_or_index)
    elif tp == int:
        return IntEditor(tag, aggregate, key_or_index, tag.valid_choices)
    elif tp == bool:
        return BoolEditor(tag, aggregate, key_or_index)
    elif tp == Path:
        return PathEditor(tag, aggregate, key_or_index)
    else:
        raise TypeError(f"Type has no editor: {tp}")
