import dataclasses
from typing import List, Any

import PySide2
from PySide2 import QtCore
from PySide2.QtCore import QAbstractTableModel, Signal, QModelIndex, Qt
from PySide2.QtGui import QKeyEvent, QBrush, QColor
from PySide2.QtWidgets import QTableView, QStyledItemDelegate, QComboBox


class ComboBoxDelegate(QStyledItemDelegate):
    """ComboBox view inside of a Table. It only shows the ComboBox when it is
       being edited. Could be used for anything, actually.
    """

    def __init__(self, model, itemlist=None):
        super().__init__(model)
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


class TableView(QTableView):
    """View to be used in association with the model; it handles a delete key and getting
    the selected item"""
    delete = Signal()
    selChanged = Signal(int)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Delete:
            self.delete.emit()
        super().keyPressEvent(event)

    def get_selected_item(self):
        """Get the selected column, only if an entire column is selected - and if more than one is,
        only consider the first."""
        sel = self.selectionModel()
        if sel.hasSelection():
            if len(sel.selectedColumns()) > 0:
                col = sel.selectedColumns()[0].column()
                return col
        return None

    def selectionChanged(self, selected, deselected):
        super().selectionChanged(selected, deselected)
        self.selChanged.emit(self.get_selected_item())


class TableModel(QAbstractTableModel):
    """This is a model which acts between a list of dataclass items a  table view.
    Currently it organises the view as one COLUMN per data item and one ROW
    per field in those items. That might seem a bit sideways, but it's because
    the canvas occupies a large area to the right in most tabs and there are more
    data fields than items.

    You must write setData() in any subclass."""

    # custom signal used when we change data
    changed = Signal()

    def __init__(self, tab, dataClass: Any, _data: List):
        """Takes the containing a tab, a dataclass,
        and a list of whatever the item dataclass is"""
        QAbstractTableModel.__init__(self)
        self.dataClass = dataClass
        self.header = dataClass.getHeader()  # get headers from static method
        self.tab = tab  # the tab we're part of
        self.d = _data  # the list of data which is our model

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        """Here we modify data in the underlying model in response to the tableview
        or any item delegates. No shortcuts here because each item needs to
        be treated differently for validation, etc. YOU NEED TO IMPLEMENT THIS."""
        pass

    def isFailed(self, item):
        """Override if you want 'failed' items to show a highlight"""
        return False

    def data(self, index, role):
        """Called by the table view to get data to show. We just convert the dataclass
        into a tuple and get the nth item, which is fine for builtin types like
        floats, ints and strings."""
        if not index.isValid():
            return None
        field = index.row()
        item = index.column()
        if role == QtCore.Qt.BackgroundRole:
            if self.isFailed(item):
                return QBrush(QColor(255, 150, 150))

        if role != QtCore.Qt.DisplayRole:
            return None
        return dataclasses.astuple(self.d[item])[field]

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = ...) -> Any:
        if role == QtCore.Qt.DisplayRole:
            # data labels down the side
            if orientation == QtCore.Qt.Vertical:
                return self.header[section]
            # channel indices along the top
            elif orientation == QtCore.Qt.Horizontal:
                return str(section)
        return None

    def rowCount(self, parent: QModelIndex) -> int:
        return len(self.header)

    def columnCount(self, parent: QModelIndex) -> int:
        return len(self.d)

    def move_left(self, n):
        """Move a row to the left. This stuff is messy."""
        if 0 < n < len(self.d):
            # I'm still not entirely sure what's going on in this line
            self.beginMoveColumns(QModelIndex(), n, n, QModelIndex(), n - 1)
            self.d[n], self.d[n - 1] = self.d[n - 1], self.d[n]
            self.endMoveColumns()
            self.changed.emit()

    def move_right(self, n):
        """Move a row to the right. This stuff is messy."""
        if n < len(self.d) - 1:
            # I'm still not entirely sure what's going on in this line
            self.beginMoveColumns(QModelIndex(), n, n, QModelIndex(), n + 2)
            self.d[n], self.d[n + 1] = self.d[n + 1], self.d[n]
            self.endMoveColumns()
            self.changed.emit()

    def add_item(self, sourceIndex=None):
        """Add a new channeldata to the end of the list - could be copy of existing item"""
        n = len(self.d)
        self.beginInsertColumns(QModelIndex(), n, n)
        if sourceIndex is None:
            new = self.dataClass()
        else:
            new = dataclasses.replace(self.d[sourceIndex])  # weird idiom, this. Does a clone and optionally modifies.
        self.d.append(new)
        self.endInsertColumns()
        self.changed.emit()
        return n

    def delete_item(self, n):
        """Remove a given channeldata"""
        if n < len(self.d):
            self.beginRemoveColumns(QModelIndex(), n, n)
            del self.d[n]
            self.endRemoveColumns()
            self.changed.emit()

    def flags(self, index: QModelIndex) -> QtCore.Qt.ItemFlags:
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled
