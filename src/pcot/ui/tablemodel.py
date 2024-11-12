import dataclasses
from typing import List, Any

import PySide2
from PySide2 import QtCore
from PySide2.QtCore import QAbstractTableModel, Signal, QModelIndex, Qt
from PySide2.QtGui import QKeyEvent, QBrush, QColor
from PySide2.QtWidgets import QTableView, QStyledItemDelegate, QComboBox, QDialog, QGridLayout, QPushButton

from pcot.parameters.taggedaggregates import TaggedListType, TaggedList, TaggedDictType
from pcot.ui.dqwidget import DQWidget


class ComboBoxDelegate(QStyledItemDelegate):
    """ComboBox view inside of a Table. It only shows the ComboBox when it is
       being edited. Could be used for anything, actually.
    """

    def __init__(self, parent, model, itemlist=None):
        super().__init__(parent)
        self.model = model
        self.itemlist = itemlist

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(self.itemlist)
        editor.setCurrentIndex(0)
        editor.installEventFilter(self)
        # normally, the editor (the temporary combobox created when we double click) only closes when we
        # hit enter or click away. This makes sure it closes when an item is modified, so the change gets
        # sent to the model.
        editor.currentIndexChanged.connect(lambda: editor.close())
        return editor

    def setEditorData(self, editor, index):
        """Set the ComboBox's current index."""
        value = index.data(QtCore.Qt.DisplayRole)
        i = editor.findText(value)
        if i == -1:
            i = 0
        editor.setCurrentIndex(i)

    def setModelData(self, editor, model, index):
        """Set the table's model's data when finished editing."""
        value = editor.currentText()
        model.setData(index, value, QtCore.Qt.EditRole)


class DQDialog(QDialog):
    """Dialog for DQ delegate"""

    def __init__(self, initial_bits, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select DQ")
        layout = QGridLayout()
        self.setLayout(layout)

        self.dqWidget = DQWidget(self, bits=initial_bits)
        layout.addWidget(self.dqWidget, 0, 0, 1, 2)

        button = QPushButton("OK")
        button.clicked.connect(self.clicked)
        layout.addWidget(button, 1, 0)
        button = QPushButton("Cancel")
        button.clicked.connect(lambda: self.reject())
        layout.addWidget(button, 1, 1)
        self.bits = initial_bits

    def get(self):
        return self.bits

    def clicked(self):
        self.bits = self.dqWidget.bits
        self.accept()


class DQDelegate(QStyledItemDelegate):
    """Delegate for editing DQ bits - pops up an editing dialog"""

    def __init__(self, parent, model):
        super().__init__(parent)
        self.model = model

    def createEditor(self, parent, option, index):
        i = index.column()
        dialog = DQDialog(self.model.tags[i].dq, parent)
        dialog.open()
        return dialog

    def setModelData(self, editor, model, index):
        if editor is None or editor.result() == QDialog.Rejected:
            print("Rejected")
        else:
            i = index.column()
            model.d[i].dq = editor.get()
            model.changed.emit()


class TableView(QTableView):
    """View to be used in association with the model; it handles a delete key and getting
    the selected item"""
    delete = Signal()
    selChanged = Signal(int)

    def setModel(self, model):
        """so we keep a record of the model ourselves"""
        super().setModel(model)
        self.model = model

    def selectItem(self, item):
        if self.model.columnItems:
            self.selectColumn(item)
        else:
            self.selectRow(item)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Delete:
            self.delete.emit()
        super().keyPressEvent(event)

    def get_selected_item(self):
        """Get the selected item, only if an entire column or row is selected - and if more than one is,
        only consider the first."""
        sel = self.selectionModel()
        if sel.hasSelection():
            if self.model.columnItems:
                if len(sel.selectedColumns()) > 0:
                    return sel.selectedColumns()[0].column()
            else:
                if len(sel.selectedRows()) > 0:
                    return sel.selectedRows()[0].row()

        return None

    def selectionChanged(self, selected, deselected):
        super().selectionChanged(selected, deselected)
        self.selChanged.emit(self.get_selected_item())


class TableModel(QAbstractTableModel):
    """This is a model which acts between a list of dataclass or taggeddict items
    and a table view. Subclasses are TableModelDataClass and TableModelTaggedAggregate.
    You must write setData() in any subclass of TableModelDataClass."""

    # custom signal used when we change data
    changed = Signal()

    def __init__(self, tab, columnItems: bool):
        """Takes the containing tab and whether items are columns and rows are fields (as in pixtest)"""
        QAbstractTableModel.__init__(self)
        self.tab = tab  # the tab we're part of
        self.columnItems = columnItems
        self.header = None  # subclass must provide

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        """Here we modify data in the underlying model in response to the tableview
        or any item delegates. No shortcuts here because each item needs to
        be treated differently for validation, etc. YOU NEED TO IMPLEMENT THIS if you subclass
        TableModelDataClass, but it should just work in TableModelTaggedAggregate"""
        pass

    def isFailed(self, item):
        """Override if you want 'failed' items to show a highlight"""
        return False

    def getItemAndField(self, index):
        if self.columnItems:
            return index.column(), index.row()
        else:
            return index.row(), index.column()

    def data(self, index, role):
        """Called by the table view to get data to show. We just convert the dataclass
        into a tuple and get the nth item, which is fine for builtin types like
        floats, ints and strings."""
        if not index.isValid():
            return None
        item, field = self.getItemAndField(index)
        if role == QtCore.Qt.BackgroundRole:
            if self.isFailed(item):
                return QBrush(QColor(255, 150, 150))

        if role != QtCore.Qt.DisplayRole:
            return None
        return self._get_data(item, field)

    def _get_data(self, item:int, field:int):
        """Given item and field indices, return the field in the item
        the immediate subclasses for dataclass and tagged dict override this"""
        pass

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.DisplayRole:
            if self.columnItems:
                # data labels down the side
                if orientation == QtCore.Qt.Vertical:
                    return self.header[section]
                # channel indices along the top
                elif orientation == QtCore.Qt.Horizontal:
                    return str(section)
            else:
                if orientation == QtCore.Qt.Vertical:
                    return str(section)
                elif orientation == QtCore.Qt.Horizontal:
                    return self.header[section]
        return None

    def itemCount(self):
        """Return the number of items in the model -
        the immediate subclasses for dataclass and tagged dict override this"""
        pass

    def rowCount(self, parent: QModelIndex) -> int:
        return len(self.header) if self.columnItems else len(self.d)

    def columnCount(self, parent: QModelIndex) -> int:
        return len(self.d) if self.columnItems else len(self.header)

    def _item_swap(self, a: int, b: int):
        """Internals of moving an item. Swaps two items.
        the immediate subclasses for dataclass and tagged dict override this"""
        pass

    def move_left(self, n):
        """Move an item to the left, or up if not columnItems. This stuff is messy."""
        if 0 < n < self.itemCount():
            if self.columnItems:
                self.beginMoveColumns(QModelIndex(), n, n, QModelIndex(), n - 1)
            else:
                self.beginMoveRows(QModelIndex(), n, n, QModelIndex(), n - 1)
            self._item_swap(n-1, n)
            if self.columnItems:
                self.endMoveColumns()
            else:
                self.endMoveRows()
            self.changed.emit()

    def move_right(self, n):
        """Move an item to the right, or down if not columnItems. This stuff is messy."""
        if n < len(self.d) - 1:
            if self.columnItems:
                self.beginMoveColumns(QModelIndex(), n, n, QModelIndex(), n + 2)
            else:
                self.beginMoveRows(QModelIndex(), n, n, QModelIndex(), n + 2)
            self._item_swap(n, n + 1)
            if self.columnItems:
                self.endMoveColumns()
            else:
                self.endMoveRows()
            self.changed.emit()

    def _create_item(self):
        """create a new item
        the immediate subclasses for dataclass and tagged dict override this"""
        pass

    def _clone_item(self, n):
        """clone an item
        the immediate subclasses for dataclass and tagged dict override this"""
        pass

    def add_item(self, sourceIndex=None):
        """Add a new channeldata to the end of the list - could be copy of existing item"""
        n = len(self.d)
        if self.columnItems:
            self.beginInsertColumns(QModelIndex(), n, n)
        else:
            self.beginInsertRows(QModelIndex(), n, n)
        if sourceIndex is None:
            new = self._create_item()
        else:
            new = self._clone_item(sourceIndex)
        self.d.append(new)
        if self.columnItems:
            self.endInsertColumns()
        else:
            self.endInsertRows()
        self.changed.emit()
        return n

    def _delete_item_internal(self, n):
        """
        Does the actual item deletion.
        The immediate subclasses for dataclass and tagged dict override this if required,
        but frankly this should work.
        """
        del self.d[n]

    def delete_item(self, n):
        """Remove a given channeldata"""
        if n < len(self.d):
            if self.columnItems:
                self.beginRemoveColumns(QModelIndex(), n, n)
            else:
                self.beginRemoveRows(QModelIndex(), n, n)
            self._delete_item_internal(n)
            if self.columnItems:
                self.endRemoveColumns()
            else:
                self.endRemoveRows()
            self.changed.emit()

    def flags(self, index: QModelIndex) -> QtCore.Qt.ItemFlags:
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled


class TableModelDataClass(TableModel):
    def __init__(self, tab, dataClass, _data: List, columnItems: bool):
        super().__init__(tab, columnItems)
        self.dataClass = dataClass
        self.d = _data  # the list of data which is our model

        self.header = dataClass.getHeader()  # get headers from static method

    def _get_data(self, item, field):
        return dataclasses.astuple(self.d[item])[field]

    def itemCount(self):
        return len(self.d)

    def _item_swap(self, a, b):
        self.d[a], self.d[b] = self.d[b], self.d[a]

    def _create_item(self):
        return self.dataClass()

    def _clone_item(self, n):
        # weird idiom, this. Does a clone and optionally modifies.
        return dataclasses.replace(self.d[n])


class TableModelTaggedAggregate(TableModel):
    """
    This is a table model that works with a TaggedList of ordered TaggedDicts - see xformgen.py for an example
    """
    def __init__(self, tab, _data: TaggedList, columnItems: bool):
        super().__init__(tab, columnItems)
        self.listType = _data.type
        self.d = _data  # the list of data which is our model
        # we have to check that the list is of TaggedDicts
        tt = self.listType.tag().type
        if not isinstance(tt, TaggedDictType):
            raise ValueError("TableModelTaggedAggregate requires a TaggedList of ordered TaggedDicts")
        self.header = tt.getHeader()  # get headers from static method

    def _get_data(self, item, field):
        # get the nth item in list
        item = self.d[item]
        # and the field in that item
        return item[field]

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        item, field = self.getItemAndField(index)

        # we need to make sure the value is of the right type - or at least that it's a string
        # or numeric appropriately. We could make the process_numeric_type method in TaggedDict
        # class handle this, but I don't want to attempt to promote strings (although int/float
        # conversion is OK) so I handle it here.

        # get the type of the field
        dictType = self.listType.tag().type
        fieldName = dictType.ordering[field]
        fieldType = dictType.tags[fieldName].type

        try:
            if fieldType == int:
                value = int(value)
            elif fieldType == float:
                value = float(value)
        except ValueError as e:
            raise ValueError(f"Value must be a number for field {fieldName} in this table") from e
        self.d[item][field] = value
        self.changed.emit()
        return True

    def itemCount(self):
        return len(self.d)

    def _item_swap(self, a, b):
        self.d[a], self.d[b] = self.d[b], self.d[a]

    def _create_item(self):
        return self.d.append_default()

    def _clone_item(self, n):
        return self.d[n].clone()

