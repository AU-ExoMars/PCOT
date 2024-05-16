import pcot
import os
from PySide2 import QtWidgets
from PySide2.QtWidgets import QAction, QMessageBox
from pcot.dataformats import envi
from pcot import ui


def test(w):
    """Function takes a PCOT main window. It finds the first selected
    node, gets its output 0, and then saves an ENVI from that image."""

    sel = w.doc.getSelection()
    if len(sel) == 0:
        ui.log("no selected node")
        return
    node = sel[0]

    directory = os.path.expanduser(pcot.config.getDefaultDir('pcotfiles'))
    print(f"directory is {directory}")
    res = QtWidgets.QFileDialog.getSaveFileName(w,
                                                "ENVI file ",
                                                os.path.expanduser(pcot.config.getDefaultDir('pcotfiles')),
                                                "ENVI files (*.hdr)")
    if res[0] != '':
        # get the output of that node
        (root, ext) = os.path.splitext(res[0])
        print(f"{res[0]}, saving to {root}")
        img = node.getOutput(0, pcot.datum.Datum.IMG)
        envi.write(root, img)


def addMenus(w):
    """Add an item to the Edit menu"""
    act = QAction("save to ENVI", parent=w)
    w.menuEdit.addAction(act)
    act.triggered.connect(lambda: test(w))


pcot.config.addMainWindowHook(addMenus)
