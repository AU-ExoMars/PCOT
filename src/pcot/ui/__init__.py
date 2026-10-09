import logging
import traceback
from datetime import datetime

import pcot.ui.mainwindow as mainwindow
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)

# Stores the QApplication if we have one. But it *only* does this for when there really is a UI.

application = None


def setApp(a):
    """Set the QApplication singleton - only for use when the PCOT GUI is running.
    There is another QApplication stored in main.py - this is always set to something.
    In the PCOT application it's this, in other programs it is created by checkApp() in
    that file."""
    global application
    application = a


def app():
    """Get the QApplication singleton if this is running the PCOT GUI"""
    return application


## show a message on the status bar
def msg(t):
    if application is not None:
        for x in mainwindow.MainUI.windows:
            x.statusBar.showMessage(t)
            x.statusBar.repaint()  # make sure the message appears!
    else:
        logger.debug(f"LOG ui.msg {t}")


def log(s, toStdout=True, timestamp=True, loglevel=logging.INFO):
    """show a message in all window logs"""

    # add timestamp, just HMS will do.
    if timestamp:
        s = f"{datetime.now().strftime('%H:%M:%S')} {s}"

    if application is not None:
        for x in mainwindow.MainUI.windows:
            x.logText.append(s)
    if toStdout:
        logger.log(loglevel, s)


def snark(s):
    """This is a high-priority temporary debugging message - we can hunt and delete them later
    (Carroll, L. & Holiday, H. (1902) The Hunting of the Snark, an Agony, in Eight Fits . New York, The Macmillan company."""
    if application is not None:
        s = f"{datetime.now().strftime('%H:%M:%S')} {s}"
        for x in mainwindow.MainUI.windows:
            x.logText.append(f'<font color="purple">{s}</font>')
    logger.debug(f"LOG snark {s}")


def error(s, tb=True):
    """show error on status bar, and log in red; will dump traceback to stdout if requested."""
    if application is not None:
        m = f'<font color="red">Error: </font> {s}'
        for x in mainwindow.MainUI.windows:
            x.logText.append(m)
        application.beep()
    logger.critical(f"ERROR {s}", exc_info=True, stack_info=True)
    msg("ERROR: {}".format(s))



def warn(s):
    """show a warning dialog"""
    if app() is not None:
        application.beep()
        QtWidgets.QMessageBox.warning(None, 'WARNING', s)
    else:
        logger.warning(f"LOG WARN {s}")


## log an XFormException
def logXFormException(node, e):
    error(f"Exception in {node.name}-{node.type.name}: {e}")
    if app() is not None:
        log(f'<font color="red">Exception in <b>{node.name}:{node.type.name}</b>: </font> {e}')


# called when a graph saved with a different version of a node is loaded
def versionWarn(n):
    if app() is not None:
        log('<font color="red">Version clash</font> in node \'{}\', type \'{}\'. Current: {}, file: {}'
            .format(n.name, n.type.name, n.type.ver, n.savedver), loglevel=logging.WARN)
        log('<font color="blue">Current MD5 hash: </font> {}'.format(n.type.md5()), loglevel=logging.WARN)
        log('<font color="blue">MD5 hash in file:</font> {}'.format(n.savedmd5), loglevel=logging.WARN)

        log("WARNING DIALOG DISABLED", loglevel=logging.WARN)
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
            .format(n.name, n.type.name, n.type.ver, n.savedver), loglevel=logging.WARN)
        log('Current MD5 hash: {}'.format(n.type.md5()), loglevel=logging.WARN)
        log('MD5 hash in file: {}'.format(n.savedmd5), loglevel=logging.WARN)


def decorateSplitter(splitter: QtWidgets.QSplitter, index: int):
    """Often splitters in Qt are really hard to see - especially true for those on the Canvas. This code makes
    them more visible, creating a double-bar handle that goes the whole width/height.
    Adapted from https://stackoverflow.com/questions/2545577/qsplitter-becoming-undistinguishable-between-qwidget-and-qtabwidget/13513631#13513631
    """
    splitter.setOpaqueResize(False)
    splitter.setChildrenCollapsible(False)

    splitter.setHandleWidth(7)
    handle = splitter.handle(index)
    layout = QtWidgets.QHBoxLayout(handle)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(_SplitterGrip(handle, splitter.orientation()))


class _SplitterGrip(QtWidgets.QWidget):
    """Fills a splitter handle, drawing two thin lines along its length with a solid block in the
    middle to show that it can be dragged. Mouse events pass through to the handle."""

    blockLength = 40

    def __init__(self, parent, orientation):
        super().__init__(parent)
        self.horizontal = orientation == Qt.Orientation.Horizontal
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def _rect(self, along, across, alongLen, acrossLen):
        """Make a rect from coordinates along and across the handle, so the drawing code
        doesn't care about orientation (a horizontal splitter has a vertical handle)."""
        if self.horizontal:
            return QtCore.QRect(across, along, acrossLen, alongLen)
        return QtCore.QRect(along, across, alongLen, acrossLen)

    def paintEvent(self, event):
        r = self.rect()
        length, thickness = (r.height(), r.width()) if self.horizontal else (r.width(), r.height())
        pal = self.palette()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # the lines
        mid = thickness // 2
        for across in (mid - 2, mid + 1):
            p.fillRect(self._rect(0, across, length, 1), pal.color(QtGui.QPalette.ColorRole.Mid))

        # the block in the middle
        blockLen = min(self.blockLength, length // 3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(pal.color(QtGui.QPalette.ColorRole.Dark))
        p.drawRoundedRect(self._rect((length - blockLen) // 2, 0, blockLen, thickness), 2, 2)
