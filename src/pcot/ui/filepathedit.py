from pathlib import Path

from PySide6.QtCore import Qt, QDir, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QFileSystemModel, QCompleter, QToolButton, QFileDialog, QWidget


class FilePathEdit(QWidget):
    FILE = 0
    DIRECTORY = 1

    pathChanged = Signal(str)

    def __init__(self, mode=FILE, filter="", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.filter = filter

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Line edit with filesystem autocomplete ---
        self.edit = QLineEdit(self)
        self.edit.setPlaceholderText("Select a file..." if mode == self.FILE
                                     else "Select a directory...")

        self.model = QFileSystemModel(self)
        self.model.setRootPath(QDir.rootPath())

        if filter!="":
            import re
            patterns = []
            matches = re.findall(r"(\*\.\w+)", filter)
            for x in matches:
                patterns.append(str(x))
            if patterns:
               self.model.setNameFilters(patterns)
               self.model.setNameFilterDisables(False)

        self.completer = QCompleter(self.model, self)

        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)

        self.edit.setCompleter(self.completer)

        # --- Browse button ---
        self.button = QToolButton(self)
        self.button.setText("…")
        self.button.clicked.connect(self.open_dialog)
        self.edit.textChanged.connect(self.pathChanged)

        layout.addWidget(self.edit)
        layout.addWidget(self.button)

    @staticmethod
    def lowest_existing_dir(dir: Path|str) -> str:
        p = Path(dir).resolve()
        while not p.is_dir():
            p = p.parent
        return str(p)

    # ---------------------------------------------------------
    # Dialog logic
    # ---------------------------------------------------------
    def open_dialog(self):
        dir = self.lowest_existing_dir(self.edit.text())
        if self.mode == self.FILE:
            path, _ = QFileDialog.getOpenFileName(self, "Select File", filter=self.filter, dir=dir)
        else:
            path = QFileDialog.getExistingDirectory(self, "Select Directory",dir=dir)

        if path:
            self.edit.setText(path)

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def path(self):
        return self.edit.text()

    def setPath(self, path):
        self.edit.setText(path)