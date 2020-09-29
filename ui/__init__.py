import traceback
from ui.mainwindow import MainUI
from PyQt5 import QtWidgets

def msg(t): # show msg on status bar
    for x in MainUI.windows:
        x.statusBar.showMessage(t)
    
def log(s):
    print("LOG:",s)
    for x in MainUI.windows:
        x.logText.append(s)
    
def error(s):
    app.beep()
    traceback.print_stack()
    msg("Error: {}".format(s))
    log('<font color="red">Error: </font> {}'.format(s))
    
def warn(s):
    app.beep()
    QtWidgets.QMessageBox.warning(None,'WARNING',s)
    
def logXFormException(node,e):
    app.beep()
    error("Exception in {}: {}".format(node.name,e))
    log('<font color="red">Exception in <b>{}</b>: </font> {}'.format(node.name,e))


# called when a graph saved with a different version of a node is loaded
def versionWarn(n):
    log('<font color="red">Version clash</font> in node \'{}\', type \'{}\'. Current: {}, file: {}'
        .format(n.name,n.type.name,n.type.ver,n.savedver))
    log('<font color="blue">Current MD5 hash: </font> {}'.format(n.type.md5()))
    log('<font color="blue">MD5 hash in file:</font> {}'.format(n.savedmd5))
    
    warn(
        """
Node '{}' was saved with a different version of the '{}' node's code.
Current version: {}
Version in file: {}
If these are the same the file may have been modified without changing the \
version numbers. See MD5 data in the log.
        """
    .format(n.name,n.type.name,n.type.ver,n.savedver))
