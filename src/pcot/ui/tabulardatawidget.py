"""
Read-only table view of the data from a TabularProvider.
"""
from typing import List, Dict, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from pcot.utils.tabular_provider import TabularProvider


class TabularDataModel(QAbstractTableModel):
    """Model holding the rows from a TabularProvider. Providers can only be iterated forwards, but
    a Qt model needs random access to rows, so we read them all in when the provider is set."""
    headers: List[str]
    rows: List[Dict[str, str]]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.headers = []
        self.rows = []

    def setProvider(self, provider: Optional[TabularProvider]):
        self.beginResetModel()
        if provider is None:
            self.headers = []
            self.rows = []
        else:
            self.headers = provider.getHeaders()
            self.rows = list(provider)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        # a row may not have every column
        return self.rows[index.row()].get(self.headers[index.column()], "")

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return str(section)


class TabularDataWidget(QtWidgets.QTableView):
    """Shows the data from a TabularProvider in a read-only table"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tableModel = TabularDataModel(self)
        self.setModel(self.tableModel)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        # row numbers aren't meaningful for most providers, so don't show them
        self.verticalHeader().setVisible(False)

    def display(self, provider: Optional[TabularProvider]):
        self.tableModel.setProvider(provider)
        self.resizeColumnsToContents()
