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


class TabularDataWidget(QtWidgets.QWidget):
    """Shows the data from a TabularProvider in a read-only table. If the provider has parameters,
    there is also a button to open an editor for them."""

    provider: Optional[TabularProvider]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.provider = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        row = QtWidgets.QHBoxLayout()
        row.addStretch()
        self.settingsButton = QtWidgets.QPushButton("Table settings...")
        self.settingsButton.setToolTip("Change how this kind of data is shown as a table")
        self.settingsButton.clicked.connect(self.settingsClicked)
        self.settingsButton.setVisible(False)
        row.addWidget(self.settingsButton)
        layout.addLayout(row)

        self.view = QtWidgets.QTableView(self)
        self.tableModel = TabularDataModel(self)
        self.view.setModel(self.tableModel)
        self.view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        # row numbers aren't meaningful for most providers, so don't show them
        self.view.verticalHeader().setVisible(False)
        layout.addWidget(self.view)

    def display(self, provider: Optional[TabularProvider]):
        self.provider = provider
        self.tableModel.setProvider(provider)
        self.view.resizeColumnsToContents()
        # only show the settings button for providers which have settings
        self.settingsButton.setVisible(provider is not None and provider.getParams() is not None)

    def settingsClicked(self):
        if self.provider is None or self.provider.getParams() is None:
            return
        # imported here to avoid a circular import
        from pcot.ui.taggedaggregates import AggregateEditorDialog
        dialog = AggregateEditorDialog(self.provider.getParams(), parent=self)
        dialog.setWindowTitle("Table settings")
        dialog.exec()   # it's modal
        if dialog.data():  # None if the user cancelled
            self.provider.setParams(dialog.data())
            # redisplay, because the settings may change the table
            self.display(self.provider)
