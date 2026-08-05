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

from PySide6 import QtWidgets
from PySide6.QtCore import QAbstractListModel, QModelIndex, QItemSelection, QItemSelectionModel
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

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
    """Interface for the owner of the preset manager - the thing which has presets. It is sometimes
    used rather hackily, for example when a preset is passed as an argument to the direct multifile loader."""

    def fetchPreset(self) -> Any:
        """Fetch the current settings as something that can be serialised"""
        pass

    def applyPreset(self, preset: Any):
        """Apply the settings from the preset"""
        pass


class PresetModel(QAbstractListModel):
    """Model for the list - it's a simple model around the list and dict.
    Presets are just dicts.
    """

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

    def importPresets(self, filename: str):
        """Import the presets from the file, adding them to existing presets"""
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                new_presets, new_preset_list = json.load(f)
                self.presets.update(new_presets)
                # add presets, removing
                [self.presetList.append(x) for x in new_preset_list if x not in self.presets]



    def addPreset(self, name, p: Dict):
        """This is generally used only in testing to add presets after the fact in a crude way.
        In most real cases, savePreset is used. We do NOT save the presets."""
        self.presets[name] = p
        self.presetList.append(name)

    def savePresetsToFile(self):
        """Write the preset model to the file"""
        with open(self.filename, 'w') as f:
            json.dump((self.presets, self.presetList), f, indent=2)

    def loadPresetByName(self, name: str) -> Any:
        """Fetch and return the raw preset data for the given name (typically a dict).
        Raises KeyError if the name is not found. This method does NOT apply the preset
        to anything - if you want that, call owner.applyPreset(result) yourself.

        (This used to take an `owner` argument and call owner.applyPreset() itself while
        returning None. That shape made it very easy to accidentally apply a preset twice -
        once inside this method, once again by a caller which (reasonably) assumed the
        return value was meant to be passed to applyPreset(). Fetch and apply are now two
        explicit steps.)
        """
        if name not in self.presets:
            raise KeyError(f"Preset {name} not found")
        return self.presets[name]

    def loadPreset(self, owner, row):
        """Load the preset at the given row and apply it to owner (calls owner.applyPreset()
        for you). This is the one place where fetch+apply are still combined in a single
        call, because the dialog only has a row index, not a name, and always wants both
        steps done together."""
        name = self.presetList[row]
        owner.applyPreset(self.loadPresetByName(name))

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
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
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
        if role == Qt.ItemDataRole.DisplayRole:
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

    def _promote_demote(self, idxs, promote:bool):
        if len(idxs) > 0:
            lst = self.presetList
            # we need to get the actual items, because the list will change between each swap, although
            # it's quite likely we'll only allow single selection.
            items = [lst[x.row()] for x in idxs]
            for x in items:
                # find the item
                idx = lst.index(x)
                # promote or demote it
                if promote:
                    if idx > 0:
                        lst[idx-1],lst[idx] = lst[idx],lst[idx-1]
                elif idx < len(lst)-1:
                    lst[idx + 1], lst[idx] = lst[idx], lst[idx + 1]
            self.presetList = lst
            self.dataChanged.emit(QModelIndex(), QModelIndex())
            # get new indices
            idxs = [lst.index(x) for x in items]
            self.savePresetsToFile()
            return [self.createIndex(x,0) for x in idxs]     # to allow the caller to re-select
        return None

    def promote(self, idxs):
        return self._promote_demote(idxs, True)

    def demote(self, idxs):
        return self._promote_demote(idxs, False)



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
        self.upButton.clicked.connect(self.promotePreset)
        self.downButton.clicked.connect(self.demotePreset)

        from pcot.assets import Icons
        self.upButton.setIcon(Icons.get("arrow-up"))
        self.downButton.setIcon(Icons.get("arrow-down"))

        self.owner = owner
        self.model = model
        self.listView.setModel(self.model)

    def _reselect(self, newSel):
        # Used in promote and demote, which return a list of QModelIndex for the moved items.
        # We then have to do this dance to move the selected items. Much simpler if we assume there's only
        # one item selected, but we don't know that for sure.
        if newSel is not None:
            selmod = QItemSelection()
            for x in newSel:
                selmod.select(x, x)
            self.listView.selectionModel().select(selmod, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Select)


    def promotePreset(self):
        self._reselect(self.model.promote(self.listView.selectedIndexes()))

    def demotePreset(self):
        self._reselect(self.model.demote(self.listView.selectedIndexes()))

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
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
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
