import pcot
import os
from PySide2 import QtWidgets
from PySide2.QtWidgets import QAction, QMessageBox
from pcot.dataformats import envi

def test(w):
    """Function takes a PCOT main window. It finds the input 0 if it can,
    and then saves an ENVI from that image."""
    
    try:
        node = w.doc.getNodeByName("input 0")
    except NameError:
        print("cannot find node")
        return
        
    res = QtWidgets.QFileDialog.getSaveFileName(w,
                                                "ENVI file ",
                                                os.path.expanduser(pcot.config.getDefaultDir('pcotfiles')),
                                                "ENVI files (*.hdr)")
    if res[0] != '':
        (root, ext) = os.path.splitext(res[0])
        # get the output of that input 0 node
        img = node.getOutput(0,pcot.datum.Datum.IMG)
        envi.write(root,img)
        
        

def addMenus(w):
    """Add an item to the Edit menu"""
    act = QAction("save to ENVI",parent=w)
    w.menuEdit.addAction(act)
    act.triggered.connect(lambda: test(w))
    

pcot.config.addMainWindowHook(addMenus)
