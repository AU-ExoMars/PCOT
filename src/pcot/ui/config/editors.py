"""
Editors for the config UI. These are widgets and tools to allow them to modify TaggedAggregate data.
"""
import dataclasses
from functools import partial
from pathlib import Path
from typing import Tuple, Optional

from PySide2 import QtWidgets
from PySide2.QtCore import Qt, QObject, QModelIndex
from PySide2.QtWidgets import QListWidgetItem

from pcot.parameters.taggedaggregates import Tag, TaggedList, TaggedDict, Maybe, TaggedListType
from pcot.ui.filepathedit import FilePathEdit


class Editor(QObject):
    def __init__(self, tag: Tag, aggregate: TaggedList | TaggedDict, key_or_index: int | str):
        """
        container - the thing containing what is to be edited; a TaggedList or a TaggedDict.
        key_or_index - for a TD, it's the key; for a TL, it's the index.
        """
        super().__init__()
        self.aggregate = aggregate
        self.key_or_index = key_or_index
        self.label=tag.description
        self.widget = None


class TextEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str):
        super().__init__(tag, container, key_or_index)
        self.widget = QtWidgets.QLineEdit()
        if container[key_or_index] is not None:
            self.widget.setText(container[key_or_index])
        # can't connect to the method directly, because the class is not a QObject
        self.widget.textChanged.connect(lambda t: self.changed(t))

    def changed(self, t):
        self.aggregate[self.key_or_index] = t


class IntEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str, range:Optional[Tuple[int,int]]):
        super().__init__(tag, container, key_or_index)
        self.widget = QtWidgets.QSpinBox()
        if not range:
            range = (0,99)  # this is the default range for a qspinbox, but we set it explicitly anyway
        self.label = f"{self.label} ({range[0]}..{range[1]})"
        self.widget.setRange(*range)
        if container[key_or_index] is not None:
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
        if container[key_or_index] is not None:
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
        if container[key_or_index] is not None:
            self.widget.setPath(str(container[key_or_index]))
        self.widget.pathChanged.connect(lambda t: self.changed(t))

    def changed(self, t):
        self.aggregate[self.key_or_index] = t


class BoolEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str):
        super().__init__(tag, container, key_or_index)
        self.widget = QtWidgets.QCheckBox("")
        if container[key_or_index] is not None:
            self.widget.setChecked(container[key_or_index])
        # can't connect to the method directly, because the class is not a QObject
        self.widget.stateChanged.connect(lambda t: self.changed(t))

    def changed(self, _):
        self.aggregate[self.key_or_index] = self.widget.isChecked()


class MaybeEditor(Editor):
    """This is a wrapper around one of the above editors that adds a "value is null" checkbox"""
    def __init__(self, tag, editor):
        super().__init__(tag, editor.aggregate, editor.key_or_index)
        self.editor = editor
        self.widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setContentsMargins(0,0,0,0)
        self.widget.setLayout(self.layout)
        self.oldvalue = self.editor.aggregate[self.editor.key_or_index]

        self.nullCheck = QtWidgets.QCheckBox("has no value")
        self.nullCheck.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.layout.addWidget(self.nullCheck)
        self.layout.addWidget(self.editor.widget)
        self.setStateFromInnerEditor()
        self.nullCheck.stateChanged.connect(lambda: self.nullChanged())

    def setStateFromInnerEditor(self):
        val = self.editor.aggregate[self.key_or_index]
        if val is None:
            self.editor.widget.setEnabled(False)
            self.nullCheck.setChecked(Qt.Checked)
        else:
            self.editor.widget.setEnabled(True)
            self.nullCheck.setChecked(Qt.Unchecked)

    def nullChanged(self):
        if self.nullCheck.isChecked():
            self.editor.widget.setEnabled(False)
            self.oldvalue = self.editor.aggregate[self.key_or_index]
            self.editor.aggregate[self.key_or_index] = None
        else:
            self.editor.widget.setEnabled(True)
            self.editor.aggregate[self.key_or_index] = self.oldvalue


class ListEditor(Editor):
    def __init__(self, parent, tag, aggregate:TaggedList|TaggedDict, key_or_index:int|str):
        super().__init__(tag, aggregate, key_or_index)
        self.widget = QtWidgets.QListWidget()
        self.lst = self.aggregate[self.key_or_index]
        self.tag = tag
        self.populate_list()

    def create_add_button(self, top:bool=False):
        add_button = QtWidgets.QPushButton("Create new item here")
        add_button.clicked.connect(partial(self.add, top))
        wi = QListWidgetItem()
        wi.setSizeHint(add_button.sizeHint())
        self.widget.addItem(wi)
        self.widget.setItemWidget(wi, add_button)

    def populate_list(self):
        self.widget.clear()
        self.buts = []
        self.create_add_button(top=True)
        for i,item in enumerate(self.lst):
            # create subeditors using the tag inside the TaggedListType
            e = createEditor(self.parent, self.tag.type.tag, self.lst, i)

            # each editor is embedded inside a QListWidgetItem along with other things
            # all of which are contained in a widget for each row

            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_widget.setLayout(row_layout)

            from pcot.assets import Icons
            (up := QtWidgets.QToolButton()).setIcon(Icons.get("arrow-up.svg"))
            row_layout.addWidget(up)
            # use of partial here to avoid both the late-binding problem of lambdas, and
            # also other weirdness possibly to do with weak references to things dying.
            up.clicked.connect(partial(self.move, i, -1))
            (down := QtWidgets.QToolButton()).setIcon(Icons.get("arrow-down.svg"))
            row_layout.addWidget(down)
            down.clicked.connect(partial(self.move, i, 1))

            (delb := QtWidgets.QPushButton()).setIcon(Icons.get("x-circle.svg"))
            row_layout.addWidget(delb)
            delb.clicked.connect(partial(self.delete, i))
            self.buts.append(delb)

            row_layout.addWidget(e.widget)
            row_layout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize) # otherwise they won't expand

            itemwidget = QtWidgets.QListWidgetItem()
            itemwidget.setSizeHint(row_widget.sizeHint()) # have to do this or the widget won't know how big it is (cheers, Copilot)
            self.widget.addItem(itemwidget)
            self.widget.setItemWidget(itemwidget, row_widget)
        self.create_add_button(top=False)

    def scroll_to_item(self, idx):
        item = self.widget.item(idx)
        self.widget.scrollToItem(item)

    def add(self, top:bool=False):
        if top:
            self.lst.prepend_default()
        else:
            self.lst.append_default()
        self.populate_list()
        self.scroll_to_item(0 if top else len(self.lst)-1)

    def move(self, idx, delta):
        print(idx,delta)

        newidx = idx + delta
        if newidx < 0 or newidx >= len(self.lst):
            return
        self.lst[idx], self.lst[newidx] = self.lst[newidx], self.lst[idx]

        self.populate_list()
        self.scroll_to_item(newidx)

    def delete(self, idx):
        print(idx)
        del self.lst[idx]
        self.populate_list()
        self.scroll_to_item(idx)



def createEditor(parent, tag: Tag, aggregate:TaggedList|TaggedDict, key_or_index:int|str):
    tp = tag.type
    if isinstance(tp, Maybe):
        # if this is a nullable, we have to wrap in an editor which will handle that.
        tp = tp.type_if_exists
        # create a new tag from the old, but using the underlying type
        tag = dataclasses.replace(tag, type=tp)
        # create the inner editor for the underlying type
        editor = createEditor(parent, tag, aggregate, key_or_index)
        # and create the wrapper
        return MaybeEditor(tag, editor)

    if isinstance(tp, TaggedListType):
        return ListEditor(parent, tag, aggregate, key_or_index)

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
        raise TypeError(f"Bad type {tp}")
