"""
Editors for the config UI. These are widgets and tools to allow them to modify TaggedAggregate data.
"""
import dataclasses
import math
from functools import partial
from pathlib import Path
from typing import Tuple, Optional
import logging

from PySide2 import QtWidgets, QtGui
from PySide2.QtCore import Qt, QObject
from PySide2.QtWidgets import QListWidgetItem, QSizePolicy, QListWidget

from pcot.parameters.taggedaggregates import Tag, TaggedList, TaggedDict, Maybe, TaggedListType, TaggedDictType, \
    TaggedVariantDictType, TaggedVariantDict
from pcot.ui.filepathedit import FilePathEdit


logger = logging.getLogger(__name__)


class Editor(QObject):
    def __init__(self, tag: Tag, aggregate: TaggedList | TaggedDict, key_or_index: int | str, handler):
        """
        container - the thing containing what is to be edited; a TaggedList or a TaggedDict.
        key_or_index - for a TD, it's the key; for a TL, it's the index.
        handler: something we can notify when a change is made (for undo, typically). It needs
           notifyBefore and notifyAfter methods which take the Editor object.
        """
        super().__init__()
        self.aggregate = aggregate
        self.key_or_index = key_or_index
        self.label=tag.description if len(tag.description)>0 else key_or_index
        self.handler = handler    # we notify this object BEFORE and AFTER we make a change!
        self.widget = None

    def notifyBefore(self):
        if self.handler and hasattr(self.handler, 'onPreChange'):
            self.handler.onPreChange(self)
    def notifyAfter(self):
        if self.handler and hasattr(self.handler, 'onPostChange'):
            self.handler.onPostChange(self)


class TextEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str, handler):
        super().__init__(tag, container, key_or_index, handler)
        self.widget = QtWidgets.QLineEdit()
        if container[key_or_index] is not None:
            self.widget.setText(container[key_or_index])
        # can't connect to the method directly, because the class is not a QObject
        self.widget.textChanged.connect(lambda t: self.changed(t))

    def changed(self, t):
        self.notifyBefore()
        self.aggregate[self.key_or_index] = t
        self.notifyAfter()


class NumericEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str, range:Optional[Tuple[int,int]], handler,
                 isfloat:bool):
        super().__init__(tag, container, key_or_index, handler)
        self.hasRange = range is not None
        self.isfloat = isfloat
        if self.hasRange:
            self.widget = QtWidgets.QDoubleSpinBox() if isfloat else QtWidgets.QSpinBox()
            self.widget.setRange(*range)
            rng = range[1]-range[0]
            # dynamic range calculator for floats
            if rng<=0 or not isfloat:
                step = 1
            else:
                exp = math.floor(math.log10(rng) - 2)
                step = 10 ** exp

            self.widget.setSingleStep(step)
            self.label = f"{self.label} ({range[0]}..{range[1]})"
            if container[key_or_index] is not None:
                self.widget.setValue(container[key_or_index])
            self.widget.valueChanged.connect(lambda v: self.changed(v))
        else:
            self.widget = QtWidgets.QLineEdit()
            self.widget.setValidator(QtGui.QDoubleValidator() if isfloat else QtGui.QIntValidator())
            self.label = f"{self.label}"
            if container[key_or_index] is not None:
                self.widget.setText(str(container[key_or_index]))
            self.widget.textChanged.connect(lambda v: self.changed(v))

    def changed(self, v):
        self.notifyBefore()
        logger.debug(f"Data now changed to {v}")
        self.aggregate[self.key_or_index] = float(v) if self.isfloat else int(v)
        self.notifyAfter()


class ComboEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str, handler):
        super().__init__(tag, container, key_or_index, handler)
        self.widget = QtWidgets.QComboBox()
        for x in tag.valid_choices:
            self.widget.addItem(x)
        if container[key_or_index] is not None:
            self.widget.setCurrentText(container[key_or_index])
        # can't connect to the method directly, because the class is not a QObject
        self.widget.currentTextChanged.connect(lambda t: self.changed(t))

    def changed(self, t):
        self.notifyBefore()
        self.aggregate[self.key_or_index] = t
        self.notifyAfter()


class PathEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str, handler):
        super().__init__(tag, container, key_or_index, handler)

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
        self.notifyBefore()
        self.aggregate[self.key_or_index] = t
        self.notifyAfter()


class BoolEditor(Editor):
    def __init__(self, tag, container:TaggedList|TaggedDict, key_or_index:int|str, handler):
        super().__init__(tag, container, key_or_index, handler)
        self.widget = QtWidgets.QCheckBox("")
        if container[key_or_index] is not None:
            self.widget.setChecked(container[key_or_index])
        # can't connect to the method directly, because the class is not a QObject
        self.widget.stateChanged.connect(lambda t: self.changed(t))

    def changed(self, _):
        self.notifyBefore()
        self.aggregate[self.key_or_index] = self.widget.isChecked()
        self.notifyAfter()


class MaybeEditor(Editor):
    """This is a wrapper around one of the above editors that adds a "value is null" checkbox"""
    def __init__(self, tag, editor, handler):
        super().__init__(tag, editor.aggregate, editor.key_or_index, handler)
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
        self.notifyBefore()
        if self.nullCheck.isChecked():
            self.editor.widget.setEnabled(False)
            self.oldvalue = self.editor.aggregate[self.key_or_index]
            self.editor.aggregate[self.key_or_index] = None
        else:
            self.editor.widget.setEnabled(True)
            self.editor.aggregate[self.key_or_index] = self.oldvalue
        self.notifyAfter()

class TallListWidget(QListWidget):
    """
    This version of a list widget will resize itself based on the size of its contained items.
    """
    def __init__(self, min_rows=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_rows = min_rows
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Recompute geometry when items change
        m = self.model()
        m.rowsInserted.connect(self.updateGeometryParents)
        m.rowsRemoved.connect(self.updateGeometryParents)

    def updateGeometryParents(self):
        super().updateGeometry()
        p = self.parent()
        while p is not None:
#            print(f"Updating geometry of {p}")
            p.updateGeometry()
            p = p.parent()

    def sizeHint(self):
        """The size hint is the sum of the hints of the widget contents"""
        hint = super().sizeHint()

        if self.count():
            heights = [self.sizeHintForRow(i) for i in range(self.count())]
            rows_h = sum(heights)
#            print(",".join([str(x) for x in heights]))
        else:
            rows_h = 24  # fallback

        min_h = rows_h + 2 * self.frameWidth()
        # for some reason it won't resize larger if the size hint when empty is less than around 100.
        prev_h = max(2*(24 + self.frameWidth()),100)
        hint.setHeight(max(prev_h, min_h))
        return hint


class ListEditor(Editor):
    def __init__(self, parent, tag, aggregate:TaggedList|TaggedDict, key_or_index:int|str, handler):
        super().__init__(tag, aggregate, key_or_index, handler)
        self.widget = TallListWidget()
        self.lst = self.aggregate[self.key_or_index]
        self.parent = parent
        self.tag = tag
        self.populate_list()

    def create_add_button(self, label:str, top:bool=False):
        add_button = QtWidgets.QPushButton(label)
        add_button.clicked.connect(partial(self.add, top))
        wi = QListWidgetItem()
        wi.setSizeHint(add_button.sizeHint())
        self.widget.addItem(wi)
        self.widget.setItemWidget(wi, add_button)

    def populate_list(self):
        self.widget.clear()
        self.buts = []
        if len(self.lst) > 0:
            self.create_add_button("Create new item at start", top=True)
        else:
            self.create_add_button("Create new item")
        for i,item in enumerate(self.lst):
            # create subeditors using the tag inside the TaggedListType
            e = createEditor(self.parent, self.tag.type.tag, self.lst, i, self.handler)

            # each editor is embedded inside a QListWidgetItem along with other things
            # all of which are contained in a widget for each row

            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_widget.setLayout(row_layout)

            idxlabel = QtWidgets.QLabel(f"{i}:")
            idxlabel.setMinimumWidth(50)
            row_layout.addWidget(idxlabel)

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

            itemwidget = QtWidgets.QListWidgetItem()
            itemwidget.setSizeHint(row_widget.sizeHint()) # have to do this or the widget won't know how big it is (cheers, Copilot)
            self.widget.addItem(itemwidget)
            self.widget.setItemWidget(itemwidget, row_widget)
        if len(self.buts) > 0:
            self.create_add_button("Create new item at end", top=False)
        self.widget.updateGeometry()

    def scroll_to_item(self, idx):
        item = self.widget.item(idx)
        self.widget.scrollToItem(item)

    def add(self, top:bool=False):
        self.notifyBefore()
        if top:
            self.lst.prepend_default()
        else:
            self.lst.append_default()
        self.populate_list()
        self.scroll_to_item(0 if top else len(self.lst)-1)
        self.notifyAfter()

    def move(self, idx, delta):
        newidx = idx + delta
        if newidx < 0 or newidx >= len(self.lst):
            return
        self.notifyBefore()
        self.lst[idx], self.lst[newidx] = self.lst[newidx], self.lst[idx]
        self.populate_list()
        self.scroll_to_item(newidx)
        self.notifyAfter()

    def delete(self, idx):
        self.notifyBefore()
        del self.lst[idx]
        self.populate_list()
        self.scroll_to_item(idx)
        self.notifyAfter()


class DictEditor(Editor):
    """Dicts are normally handled using layoutDict in the main configui.py module, but sometimes
    they are nested inside lists. That's when this editor gets used. It's deeply messy, and I apologise;
    really configui.py's code should be refactored to use this."""
    def __init__(self, parent, tag, aggregate:TaggedList|TaggedDict, key_or_index:int|str, handler):
        super().__init__(tag, aggregate, key_or_index, handler)

        from pcot.ui.taggedaggregates import AggregateEditorWidget
        assert isinstance(aggregate[key_or_index], TaggedDict)
        self.widget = AggregateEditorWidget(aggregate[key_or_index], handler=handler, parent=parent, internal_editor=True)


class WrapperWidget(QtWidgets.QWidget):
    """Widget that acts as a wrapper around another which can be replaced. This is used
    in the VariantDictEditor when the internal dict we're editing gets switched out for
    another with different fields."""
    def __init__(self):
        super().__init__()
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.widget = None

    def setWidget(self, new_widget):
        if self.widget:
            self.layout.takeAt(0)
            self.widget.deleteLater()
        self.widget = new_widget
        self.layout.addWidget(new_widget)

    def sizeHint(self):
        if self.widget:
            return self.widget.sizeHint()
        else:
            return super().sizeHint()


class VariantEditor(Editor):
    """This is a weird one, because it's like a dict editor but it can be one of several different dicts.
    There's a special field all the dicts share which say what kind of dict it is."""
    def __init__(self, parent, tag, aggregate:TaggedList|TaggedDict, key_or_index:int|str, handler):
        super().__init__(tag, aggregate, key_or_index, handler)
        self.variant: TaggedVariantDict= aggregate[self.key_or_index]
        self.parent = parent
        self.handler = handler
        self.current_type_name = None

        self.type_object = self.variant.type
        self.discriminator_field = self.type_object.discriminator_field

        self.saved_dicts = {}

        # we're just going to put a single widget in a box, and then switch it from time to time
        self.widget = WrapperWidget()
        self.currentEditorWidget = None
        self.createDictEditor()

    def createDictEditor(self):
        """Create the appropriate kind of dict editor"""
        from pcot.ui.taggedaggregates import AggregateEditorWidget
        # get the child dict we want to edit
        child = self.variant.get()
        if child is None:
            raise Exception("trying to edit an empty variant dict")

        # we create the child widget here. Note that I'm using this as the change handler, and delegating to the actual
        # handler (typically the dialog) so we can catch the discriminator changing.
        self.currentEditorWidget = AggregateEditorWidget(child, handler=self, parent=self.parent, internal_editor=True)
        self.widget.setWidget(self.currentEditorWidget)

        # stash the type name
        self.current_type_name = self.getTypeNameForVariantDict()
        # and also stash this dict!
        self.saved_dicts[self.current_type_name] = child

    def getTypeNameForVariantDict(self):
        d = self.variant.type.discriminator_field
        return self.variant.get()[d]

    def onPreChange(self, editor):
        # intercept the pre-change message and then pass it on.
        self.notifyBefore()

    def onPostChange(self, editor):
        new_type_name = self.getTypeNameForVariantDict()
        if new_type_name != self.current_type_name:
            logger.debug(f"Type changed to {new_type_name}")
            # stash the variant so we can go back to it, but remember reset its discriminator - the editor will have
            # just changed it!
            child = self.variant.get()
            child[self.discriminator_field] = self.current_type_name
            self.saved_dicts[self.current_type_name] = child
            self.current_type_name = new_type_name
            # At the moment, the TaggedVariantDict doesn't notice that the discriminator has changed. We need to force it.
            # We go back to an old dict if we have one (we'll automatically pick up the type from the discriminator)
            # or create completely fresh data otherwise
            if new_type_name in self.saved_dicts:
                self.variant.set(self.saved_dicts[new_type_name])
            else:
                self.variant.force_create_child(new_type_name)
            self.createDictEditor()
        self.notifyAfter()




def createEditor(parent, tag: Tag, aggregate:TaggedList|TaggedDict, key_or_index:int|str, handler):
    """This is called from layoutDict in AggregateEditorWidget to create an editor for a given field
    inside a tagged aggregate. It will recurse if you happen to create a list or dict editor."""
    tp = tag.type
    if isinstance(tp, Maybe):
        # if this is a nullable, we have to wrap in an editor which will handle that.
        tp = tp.type_if_exists
        # create a new tag from the old, but using the underlying type
        tag = dataclasses.replace(tag, type=tp)
        # create the inner editor for the underlying type
        editor = createEditor(parent, tag, aggregate, key_or_index, handler)
        # and create the wrapper
        return MaybeEditor(tag, editor, handler)

    if isinstance(tp, TaggedListType):
        return ListEditor(parent, tag, aggregate, key_or_index, handler)
    elif isinstance(tp, TaggedDictType):
        return DictEditor(parent, tag, aggregate, key_or_index, handler)
    elif isinstance(tp, TaggedVariantDictType):
        return VariantEditor(parent, tag, aggregate, key_or_index, handler)

    elif tp == str:
        if tag.valid_choices:
            return ComboEditor(tag, aggregate, key_or_index, handler)
        else:
            return TextEditor(tag, aggregate, key_or_index, handler)
    elif tp == int:
        return NumericEditor(tag, aggregate, key_or_index, tag.valid_choices, handler, False)
    elif tp == float:
        return NumericEditor(tag, aggregate, key_or_index, tag.valid_choices, handler, True)
    elif tp == bool:
        return BoolEditor(tag, aggregate, key_or_index, handler)
    elif tp == Path:
        return PathEditor(tag, aggregate, key_or_index, handler)
    else:
        raise TypeError(f"Bad type {tp}")
