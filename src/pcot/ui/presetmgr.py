"""
A "generic" preset manager dialog/model

Presets are just dicts of values and must be fully serialisable. It's up to the caller
to interpret the presets and apply them to the document, and to convert its data back
to a dict.

There is a model component which knows the filename, and a dialog component which
knows the model. The model loads the file at initialisation and saves it when the
dialog is closed and when presets are added/removed/renamed.

Finally, the model must be linked to the owner of the presets, which is responsible
for fetching the current settings and applying the new settings. It is the "thing
which has the presets", such as the MultifileInputMethod.


"""
import json
import os
from typing import Any, Dict, List

from PySide2 import QtWidgets
from PySide2.QtCore import QAbstractListModel, QModelIndex
from PySide2.QtGui import Qt
from PySide2.QtWidgets import QDialog, QMessageBox

from pcot.ui import uiloader, namedialog
from pcot.ui.help import md2html, showHelpDialog

HELPTEXT = """
# Preset Manager
This allows you to save and load presets for the current dialog. A preset is a set of values
that are commonly used together. For example, the Multifile input has a lot of settings describing
how raw images can be loaded. The buttons work as follows:

- Load: Load the selected preset. This will overwrite the current settings.
- Save: Save the current settings as a new preset.
- Delete: Delete the selected preset. 
- Rename: Rename the selected preset.
- Done: Close this dialog.
"""


class PresetOwner:
    """Interface for the owner of the preset manager"""

    def fetchPreset(self) -> Any:
        """Fetch the current settings as something that can be serialised"""
        pass

    def applyPreset(self, preset: Any):
        """Apply the settings from the preset"""
        pass


class PresetModel(QAbstractListModel):
    """Model for the list - it's a simple model around the list and dict"""

    presetList: List[str]  # list of preset names
    presets: Dict[str, Any]  # dict of presets

    def __init__(self, parent, filename: str):
        super().__init__(parent)
        self.presets = {}
        self.presetList = []
        # for now, just assume the presets are in a JSON file in the home directory
        if not filename.endswith('.json'):
            filename += '.json'
        self.filename = os.path.expanduser("~/" + filename)
        self.loadPresetsFromFile()

    def loadPresetsFromFile(self):
        """Read the preset model from the file"""
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                self.presets, self.presetList = json.load(f)
                if not isinstance(self.presets, dict):
                    raise Exception(f"Presets file {self.filename} does not contain a dictionary")
        else:
            self.presets = {}
            self.presetList = []

    def savePresetsToFile(self):
        """Write the preset model to the file"""
        with open(self.filename, 'w') as f:
            json.dump((self.presets, self.presetList), f, indent=2)

    def loadPresetByName(self, owner, preset: str):
        """Load a preset by name"""
        if preset not in self.presets:
            raise KeyError(f"Preset {preset} not found")
        owner.applyPreset(self.presets[preset])

    def loadPreset(self, owner, row):
        """Load the preset at the given row. This is called from the dialog - it then
        applies the preset to the owner."""
        preset = self.presetList[row]
        self.loadPresetByName(owner, preset)

    def savePreset(self, owner, selectedName=None):
        """Save the current settings as a new preset. It fetches the settings from the owner
        and adds them to the list and dict of presets under a generated name. It then saves
        the presets to the file. If a name is given, it uses that as the name. If the name
        is already in use, it asks for confirmation to overwrite."""

        # if a preset is selected, use that as the name
        name = selectedName

        # if not, generate a new name
        if name is None:
            i = 1
            while (name := f"preset{i}") in self.presets:
                i += 1

        data = owner.fetchPreset()
        # ask for a name (or for modification of the suggested name)
        ok, name = namedialog.do(name, "Save Preset", "Preset name:")
        if not ok:
            return False

        # if the name is already in use, ask for confirmation
        if name in self.presets:
            if QMessageBox.question(owner, "Overwrite preset", f"Preset {name} already exists. Overwrite?",
                                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return False
            self.presets[name] = data
        else:
            end = len(self.presets)
            self.beginInsertRows(QModelIndex(), end, end)
            self.presets[name] = data
            self.presetList.append(name)
            self.endInsertRows()
        self.savePresetsToFile()
        return True

    def rename(self, row, newname):
        if newname not in self.presets:
            oldname = self.presetList[row]
            self.presets[newname] = self.presets.pop(oldname)
            self.presetList[row] = newname
            self.savePresetsToFile()
            self.dataChanged.emit(self.index(row), self.index(row))

    def rowCount(self, parent):
        return len(self.presets)

    def data(self, index: QModelIndex, role: int):
        if role == Qt.DisplayRole:
            if index.row() < len(self.presetList):
                return self.presetList[index.row()]
        return None

    def delete(self, indexes):
        # delete all selected presets
        for idx in indexes:
            if idx.row() < len(self.presetList):
                self.beginRemoveRows(QModelIndex(), idx.row(), idx.row())
                del self.presets[self.presetList[idx.row()]]
                del self.presetList[idx.row()]
                self.endRemoveRows()
        self.savePresetsToFile()


class PresetDialog(QDialog):
    """A dialog for managing presets. It's a simple list of presets, with buttons to load, save
    and delete them (not yet implemented).

    Because the presets are actually stored in this dialog, it breaks MVC. Best make
    sure you don't have more than one of these open at once."""

    # we could use OrderedDict, but the random access methods for that
    # are useless. To have ordering, we'll just use a list of keys.

    def __init__(self, parent, title, model: PresetModel, owner: PresetOwner):
        super().__init__(parent)

        self.setWindowTitle(title)
        uiloader.loadUi('presets.ui', self)
        self.doneButton.pressed.connect(lambda: self.close())
        self.saveButton.pressed.connect(self.savePreset)
        self.loadButton.pressed.connect(self.loadPreset)
        self.deleteButton.pressed.connect(self.deletePreset)
        self.renameButton.pressed.connect(self.renamePreset)
        self.helpButton.pressed.connect(lambda: showHelpDialog(self, "Presets", HELPTEXT))
        self.listView.doubleClicked.connect(self.loadPreset)

        self.owner = owner
        self.model = model
        self.listView.setModel(self.model)

    def loadPreset(self):
        idxs = self.listView.selectedIndexes()
        if len(idxs) > 0:
            idx = idxs[0]
            self.model.loadPreset(self.owner, idx.row())

    def savePreset(self):
        # get the selected name for if we're doing an overwrite
        idxs = self.listView.selectedIndexes()
        if len(idxs) > 0:
            idx = idxs[0]
            name = self.model.presetList[idx.row()]
        else:
            name = None
        self.model.savePreset(self.owner, name)

    def deletePreset(self):
        if QMessageBox.question(self, "Delete preset", "Are you sure you want to delete the selected preset?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.model.delete(self.listView.selectedIndexes())

    def renamePreset(self):
        idxs = self.listView.selectedIndexes()
        if len(idxs) > 0:
            idx = idxs[0]
            # get the name of the preset
            oldname = self.model.presetList[idx.row()]
            rv, newname = namedialog.do(oldname)
            if rv:
                self.model.rename(idx.row(), newname)
