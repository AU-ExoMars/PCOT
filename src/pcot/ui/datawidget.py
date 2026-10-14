"""
Data widget that shows either a text view or a canvas view of the data.
"""
import os

from PySide6 import QtWidgets

import pcot
from pcot import ui
from pcot.datum import Datum
from pcot.datumexceptions import CannotSerialiseDatumType
from pcot.ui.canvas import Canvas
from pcot.utils import SignalBlocker
from pcot.utils.text import generateIndenting


class DataWidget(QtWidgets.QWidget):
    DATA = 0
    SOURCES = 1

    def __init__(self, parent, source_section=False, save_button=None):
        """source_section shows the type and data/sources controls; save_button adds a "Save..." button
        (PARC, or CSV for tables) and defaults to following source_section."""
        super().__init__(parent)
        if save_button is None:
            save_button = source_section

        outer = QtWidgets.QVBoxLayout(self)
        self.setLayout(outer)

        # contains the source and item type widgets
        inner = QtWidgets.QHBoxLayout()
        lab = QtWidgets.QLabel("Type:")
        inner.addWidget(lab)
        self.typeEdit = QtWidgets.QLineEdit()
        self.typeEdit.setReadOnly(True)
        inner.addWidget(self.typeEdit)
        self.dispTypeCombo = QtWidgets.QComboBox()
        self.dispTypeCombo.addItem("Data")
        self.dispTypeCombo.addItem("Sources")
        self.dispTypeCombo.currentIndexChanged.connect(self.dispTypeChanged)
        inner.addWidget(self.dispTypeCombo)

        # only add that inner layout if we want to display source and type
        if source_section:
            outer.addLayout(inner)

        if save_button:
            self.saveButton = QtWidgets.QPushButton("Save...")
            self.saveButton.clicked.connect(self.saveButtonClicked)
            if source_section:
                inner.addWidget(self.saveButton)
            else:
                # no source section to put it in, so give it a row of its own
                row = QtWidgets.QHBoxLayout()
                row.addStretch()
                row.addWidget(self.saveButton)
                outer.addLayout(row)
        else:
            self.saveButton = None

        self.canvas = Canvas(self)
        self.text = QtWidgets.QTextEdit(self)
        outer.addWidget(self.canvas)
        outer.addWidget(self.text)
        self.text.setVisible(False) # either the canvas or text will become visible..

        self.dispType = self.DATA
        self.datum = None

    # file formats data can be saved in: name filter -> extension
    PARC_FILTER = "PARC files (*.parc)"
    CSV_FILTER = "CSV files (*.csv)"
    EXTENSIONS = {PARC_FILTER: "parc", CSV_FILTER: "csv"}

    def saveFilters(self):
        """The name filters for the formats the current datum can be saved in; empty if it can't be saved"""
        d = self.datum
        if d is None or d.isNone():
            return []
        filters = []
        if d.tp == Datum.TABLE:
            filters.append(self.CSV_FILTER)
        if d.tp.canSerialise():
            filters.append(self.PARC_FILTER)
        return filters

    def saveButtonClicked(self):
        """Save the datum, as the 'main' item in a new PARC file or (for tables) as CSV"""
        filters = self.saveFilters()
        if not filters:
            return

        # images go with the images saved from canvases, everything else has its own location
        dirName = "savedimages" if self.datum.isImage() else "saveddata"
        dlg = QtWidgets.QFileDialog(self, f"Save {self.datum.tp.name}",
                                    os.path.expanduser(pcot.config.getDefaultDir(dirName)))
        dlg.setOptions(pcot.config.getFileDialogOptions())
        dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        dlg.setNameFilters(filters)
        # adds the extension if the user doesn't, and does so before checking whether to overwrite
        dlg.setDefaultSuffix(self.EXTENSIONS[filters[0]])
        dlg.filterSelected.connect(lambda f: dlg.setDefaultSuffix(self.EXTENSIONS[f]))
        if not dlg.exec():
            return
        path = dlg.selectedFiles()[0]
        pcot.config.setDefaultDir(dirName, os.path.dirname(os.path.realpath(path)))

        # an explicit .parc or .csv extension wins over the selected filter, if we can save in that format
        ext = os.path.splitext(path)[1][1:].lower()
        available = [self.EXTENSIONS[f] for f in filters]
        if ext in self.EXTENSIONS.values() and ext not in available:
            ui.warn(f"Data of type '{self.datum.tp.name}' cannot be saved as {ext.upper()}.")
            return
        if ext not in available:
            # some other extension (e.g. .txt) - use the format of the selected filter
            ext = self.EXTENSIONS[dlg.selectedNameFilter()]

        try:
            if ext == "csv":
                with open(path, "w", newline="") as f:
                    f.write(str(self.datum.val))  # the same CSV that batch outputs write for tables
            else:
                desc, ok = QtWidgets.QInputDialog.getText(self, "Description",
                                                          "Enter text description (optional):",
                                                          QtWidgets.QLineEdit.EchoMode.Normal, "")
                if not ok:
                    ui.log("save cancelled")
                    return
                # an empty description means "use the default", which is a string representation of the datum
                self.datum.save(path, "main", append=False, description=desc if desc != "" else None)
        except CannotSerialiseDatumType:
            ui.warn(f"Data of type '{self.datum.tp.name}' cannot be saved as a PARC.")
            return
        except Exception as e:
            ui.error(f"Could not save {path}: {e}")
            return
        ui.log(f"Saved as {path}")

    def dispTypeChanged(self, i):
        self.dispType = i
        self.refresh()

    def display(self, d):
        self.datum = d
        self.refresh()

    def refresh(self):
        d = self.datum
        if self.datum is None:
            self.text.setText("No data present")
            self.typeEdit.setText("unconnected")
            canvVis = False
        else:
            self.typeEdit.setText(str(d.tp))
            if self.dispType == self.SOURCES:
                self.text.setText(generateIndenting(d.sources.long()))
                canvVis = False
            elif d.isImage():
                self.canvas.display(d.val)
                canvVis = True
            else:
                self.text.setText(str(d.val))
                canvVis = False

        self.canvas.setVisible(canvVis)
        self.text.setVisible(not canvVis)

        if self.saveButton is not None:
            canSave = len(self.saveFilters()) > 0
            self.saveButton.setEnabled(canSave)
            if d is not None and not d.isNone() and not canSave:
                self.saveButton.setToolTip(f"Data of type '{d.tp.name}' cannot be saved")
            else:
                self.saveButton.setToolTip("")

        with SignalBlocker(self.dispTypeCombo):
            self.dispTypeCombo.setCurrentIndex(self.dispType)
