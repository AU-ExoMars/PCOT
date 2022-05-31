import logging
import traceback
import pcot.ui.mainwindow as mainwindow
from PySide2 import QtWidgets

logger = logging.getLogger(__name__)

# Stores the QApplication if we have one.

application = None


def setApp(a):
    global application
    application = a


def app():
    return application


## show a message on the status bar
def msg(t):
    if application is not None:
        for x in mainwindow.MainUI.windows:
            x.statusBar.showMessage(t)
            x.statusBar.repaint()   # make sure the message appears!
    else:
        logger.info(f"LOG MSG {t}")


## show a message in all window logs
def log(s, toStdout=True):
    if application is not None:
        for x in mainwindow.MainUI.windows:
            x.logText.append(s)
    if toStdout:
        logger.info(f"LOG MSG {s}")


## show error on status bar, and log in red; will dump traceback to stdout if requested.
def error(s, tb=True):
    if app() is not None:
        application.beep()
        log('<font color="red">Error: </font> {}'.format(s))
    if tb:
        traceback.print_stack()
    msg("ERROR: {}".format(s))


## show a warning dialog 
def warn(s):
    if app() is not None:
        application.beep()
        QtWidgets.QMessageBox.warning(None, 'WARNING', s)
    else:
        logger.warn(f"LOG WARN {s}")


## log an XFormException
def logXFormException(node, e):
    error(f"Exception in {node.name}-{node.type.name}: {e}")
    if app() is not None:
        log(f'<font color="red">Exception in <b>{node.name}:{node.type.name}</b>: </font> {e}')
        print(traceback.format_exc())


# called when a graph saved with a different version of a node is loaded
def versionWarn(n):
    if app() is not None:
        log('<font color="red">Version clash</font> in node \'{}\', type \'{}\'. Current: {}, file: {}'
            .format(n.name, n.type.name, n.type.ver, n.savedver))
        log('<font color="blue">Current MD5 hash: </font> {}'.format(n.type.md5()))
        log('<font color="blue">MD5 hash in file:</font> {}'.format(n.savedmd5))

        log("WARNING DIALOG DISABLED")
        return

        warn(
            """
    Node '{}' was saved with a different version of the '{}' node's code.
    Current version: {}
    Version in file: {}
    If these are the same the file may have been modified without changing the \
    version numbers. See MD5 data in the log.
            """
                .format(n.name, n.type.name, n.type.ver, n.savedver))
    else:
        log('Version clash in node \'{}\', type \'{}\'. Current: {}, file: {}'
            .format(n.name, n.type.name, n.type.ver, n.savedver))
        log('Current MD5 hash: {}'.format(n.type.md5()))
        log('MD5 hash in file: {}'.format(n.savedmd5))

