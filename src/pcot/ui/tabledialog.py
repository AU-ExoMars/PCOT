import logging
from PySide2 import QtWidgets, QtCore

from pcot.utils.table import Table

logger = logging.getLogger(__name__)


class TableDialog(QtWidgets.QDialog):
    """
    This is a handy class for displaying one of our Table objects in a dialog.
    """
    def __init__(self, title, table: Table):
        super().__init__(None, QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        self.setWindowTitle(title)
        tabwidg = QtWidgets.QTableWidget()

        ok = QtWidgets.QPushButton("OK")
        ok.clicked.connect(self.accept)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(tabwidg)
        layout.addWidget(ok)
        self.setLayout(layout)

        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)

        # add the headers to the table
        tabwidg.setColumnCount(len(table.keys()))
        for i, key in enumerate(table.keys()):
            tabwidg.setHorizontalHeaderItem(i, QtWidgets.QTableWidgetItem(key))
        tabwidg.verticalHeader().hide()

        # now the rows
        tabwidg.setRowCount(len(table))
        for i, row in enumerate(table):
            for j, value in enumerate(row):
                item = QtWidgets.QTableWidgetItem(str(value))
                tabwidg.setItem(i, j, item)

        tabwidg.resizeColumnsToContents()
        tabwidg.resizeRowsToContents()

        # resize the dialog to fit the table - this is phenomenally hacky.
        scrollbar_width = tabwidg.verticalScrollBar().sizeHint().width() if tabwidg.verticalScrollBar().isVisible() else 0
        widths = [tabwidg.columnWidth(i) for i in range(tabwidg.columnCount())]
        logger.info(f"Column widths: {widths}")
        totalwidth = sum([tabwidg.columnWidth(i) for i in range(tabwidg.columnCount())])
        logger.info(f"Total width of table columns: {totalwidth}")
        totalwidth += tabwidg.verticalHeader().width()
        totalwidth += tabwidg.frameWidth() * 2 + scrollbar_width + 25

        self.resize(totalwidth, self.sizeHint().height())
