import logging
import traceback
import pcot.ui.mainwindow as mainwindow
from PySide2 import QtWidgets
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QMessageBox
from pcot.ui.help import markdownWrapper

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
            x.statusBar.repaint()  # make sure the message appears!
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


def decorateSplitter(splitter: QtWidgets.QSplitter, index: int):
    """Often splitters in Qt are really hard to see - especially true for those on the Canvas. This code makes
    them more visible, creating a double-bar handle that goes the whole width/height.
    Adapted from https://stackoverflow.com/questions/2545577/qsplitter-becoming-undistinguishable-between-qwidget-and-qtabwidget/13513631#13513631
    """
    gripLength = 1200
    gripWidth = 2
    grips = 2

    splitter.setOpaqueResize(False)
    splitter.setChildrenCollapsible(False)

    splitter.setHandleWidth(7)
    handle = splitter.handle(index)
    layout = QtWidgets.QHBoxLayout(handle)
    layout.setSpacing(0)
    layout.setMargin(0)
    if splitter.orientation() == Qt.Horizontal:
        for i in range(grips):
            line = QtWidgets.QFrame(handle)
            line.setMinimumSize(gripWidth, gripLength)
            line.setMaximumSize(gripWidth, gripLength)
            line.setFrameShape(QtWidgets.QFrame.StyledPanel)
            layout.addWidget(line)
    else:
        layout.addStretch()
        vbox = QtWidgets.QVBoxLayout();
        for i in range(grips):
            line = QtWidgets.QFrame(handle)
            line.setMinimumSize(gripWidth, gripLength)
            line.setMaximumSize(gripWidth, gripLength)
            line.setFrameShape(QtWidgets.QFrame.StyledPanel)
            vbox.addWidget(line)
        layout.addWidget(vbox)
        layout.addStretch()


def pyperclipErrorDialog():
    """sometimes we need to actually pop up a dialog to make sure the error is noticed"""

    errortxt = """*Assuming your error was "Pyperclip could not find a copy/paste mechanism for your system":*
    
    PCOT uses Pyperclip for clipboard operations. On Mac and Windows this is Just Works.
    On Linux, it requires a little more to be done. You can fix this by installing one of the copy/paste
    mechanisms:

    * ```sudo apt-get install xsel``` to install the xsel utility.
    * ```sudo apt-get install xclip``` to install the xclip utility.
    * ```pip install gtk``` to install the gtk Python module.
    * ```pip install PyQt4``` to install the PyQt4 Python module. 
    """

    errortxt = markdownWrapper('\n'.join([x.strip() for x in errortxt.split('\n')]))

    QMessageBox.critical(None, "Pyperclip error", errortxt)
