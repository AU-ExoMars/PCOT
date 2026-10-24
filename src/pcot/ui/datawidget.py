"""
Data widget that shows a text view, a canvas view or a table view of the data.
"""
import os
from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets

import pcot
from pcot import ui
from pcot.datum import Datum
from pcot.datumexceptions import CannotSerialiseDatumType
from pcot.ui.canvas import Canvas
from pcot.ui.tabulardatawidget import TabularDataWidget
from pcot.utils import SignalBlocker
from pcot.utils.text import generateIndenting


class DataWidget(QtWidgets.QWidget):
    # these are the types of the main display - we're viewing either data in different ways or sources
    DISP_IMAGE = 0
    DISP_TABLE = 1
    DISP_TEXT = 2
    DISP_SOURCES = 10
    
    dispType: int   # DISP_ value

    displayingSources: bool     # true if we're displaying sources

    # widgets
    typeEdit: QtWidgets.QLineEdit
    dispTypeCombo: QtWidgets.QComboBox
    saveButton: Optional[QtWidgets.QPushButton]
    canvas: Canvas
    text: QtWidgets.QTextEdit
    table: TabularDataWidget
    

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
        self.text.setReadOnly(True)
        self.table = TabularDataWidget(self)

        outer.addWidget(self.canvas)
        outer.addWidget(self.text)
        outer.addWidget(self.table)

        self.displayingSources = False
        self.setDispType(self.DISP_TEXT)  # default value
        self.datum = None

    def setDispType(self, subtype:int):
        self.dispType = subtype
        self.canvas.setVisible(self.dispType == self.DISP_IMAGE)
        self.text.setVisible(self.dispType == self.DISP_TEXT or self.dispType == self.DISP_SOURCES)
        self.table.setVisible(self.dispType == self.DISP_TABLE)


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
        if d.tp.canProvideTable():
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
                self.datum.tp.writeCSV(Path(path), self.datum)
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
        self.displayingSources = i==1
        self.refresh()

    def display(self, d):
        self.datum = d
        self.refresh()

    def refresh(self):
        d = self.datum
        if self.datum is None:
            # really this shouldn't happen; callers should provide Datum.null
            self.text.setText("No data present")
            self.typeEdit.setText("unconnected")
            self.setDispType(self.DISP_TEXT)
        else:
            self.typeEdit.setText(str(d.tp))
            if self.displayingSources:
                self.setDispType(self.DISP_SOURCES)
                self.text.setText(generateIndenting(d.sources.long()))
            elif d.isImage():
                self.setDispType(self.DISP_IMAGE)
                self.canvas.display(d.val)
            elif d.tp.canProvideTable() and not d.isNone():
                try:
                    self.table.display(d.tp.getTabularProvider(d))
                    self.setDispType(self.DISP_TABLE)
                except Exception as e:
                    # e.g. data the provider can't lay out as a table; show why rather than a stale table
                    self.table.display(None)
                    self.setDispType(self.DISP_TEXT)
                    self.text.setText(f"Cannot show as a table: {e}")
            else:
                self.setDispType(self.DISP_TEXT)
                self.text.setText(str(d.val))

        if self.saveButton is not None:
            canSave = len(self.saveFilters()) > 0
            self.saveButton.setEnabled(canSave)
            if d is not None and not d.isNone() and not canSave:
                self.saveButton.setToolTip(f"Data of type '{d.tp.name}' cannot be saved")
            else:
                self.saveButton.setToolTip("")

        with SignalBlocker(self.dispTypeCombo):
            self.dispTypeCombo.setCurrentIndex(1 if self.displayingSources else 0)
