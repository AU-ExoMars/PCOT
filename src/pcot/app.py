"""
This is the file which creates and runs the PCOT user interface
"""
import os
from pathlib import Path

from PySide6 import QtWidgets
from PySide6.QtCore import QCommandLineParser, QCommandLineOption
import logging
import os
import getpass
import sys

import pcot.config
import pcot.ui.mainwindow
from pcot.document import Document
from pcot.ui import collapser

logger = logging.getLogger(__name__)

app = None

def setup_qt_platform():
    # only bother with this check on Linux.
    if not sys.platform.lower().startswith('linux'):
        return

    uid = os.getuid()
    wayland_socket = f"/run/user/{uid}/wayland-0"
    has_display = bool(os.environ.get("DISPLAY"))
    has_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))

    # No X11. Maybe headless, but need to check Wayland
    if not has_display:
        if has_wayland:
            # Wayland but no socket; that's no good.
            if not os.path.exists(wayland_socket):
                os.environ["QT_QPA_PLATFORM"] = "offscreen"
                return
        else:
            # No X11 and no Wayland - definitely headless
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
            return

    # We have a working display. GNOME under Wayland fails to give Qt dialogs a
    # server-side decoration (they render borderless and can overlap the main
    # window - see PYSIDE6_MIGRATION_TODO.md), which forcing XWayland works around.
    # Let the config override this since it's only confirmed on GNOME so far.
    override = pcot.config.data.qt_platform if pcot.config.data is not None else "auto"
    if override == "xcb":
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    elif override == "auto" and not has_display and has_wayland:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if "gnome" in desktop:
            os.environ["QT_QPA_PLATFORM"] = "xcb"

def checkApp():
    """Makes sure an app exists - we can't run certain code without one, and we often
    won't have one if we're not using a GUI. Note that the UI package also stores this
    if we are running the PCOT program."""

    setup_qt_platform()    

    global app
    if app is None:
        app = QtWidgets.QApplication()


def run(file):
    """the main function: loads any file specified, opens a mainwindow and runs its code.
    Command line parsing is done in main, which calls this."""

    global app

    setup_qt_platform()

    # note that we don't use Qt to process the args. This is just so Qt could
    # potentially use its internal arguments.
    app = QtWidgets.QApplication(sys.argv)
    if sys.platform.lower().startswith('win'):
        # Qt 6.7+ defaults to the "Windows11" style on Windows 11, which uses wider
        # side-by-side spin box buttons instead of the old compact stacked arrows.
        # Fusion keeps the compact spin boxes, and unlike "windowsvista" (which is
        # light-only) it is palette-driven, so it can follow the system dark mode.
        # macOS and Linux use their own native/Fusion styles and are unaffected by
        # this, so leave them be.
        app.setStyle("fusion")
    app.setApplicationVersion(pcot.__fullversion__)  # this comes from the VERSION.txt file
    app.setApplicationName("PCOT")
    app.setOrganizationName('Aberystwyth University')
    app.setOrganizationDomain('aber.ac.uk')
    pcot.ui.setApp(app)

    pcot.config.main_app_running = True
    pcot.setup()

    # create a document either ab initio or from a file, depending on file and config.
    if file is not None:
        path = Path(file)
        if not path.is_file() or path.suffix != ".pcot":
            logger.error(f"'{file}' is not a PCOT file or subcommand - type 'pcot -h' for help")
            sys.exit(1)
        else:
            doc = Document(file)
    else:
        loadfile = pcot.config.data.loadfile
        if loadfile and loadfile != "" and loadfile != ".": # "." because it's a Path which can't be empty
            doc = Document(os.path.expanduser(loadfile))
        else:
            doc = Document()
            doc.importFromConfigArchives()  # import faves and macros from files in the config settings

    # Create an instance of a main window on that document
    # Autolayout not done by default - the user might have arranged things how they like.
    window = pcot.ui.mainwindow.MainUI(doc, doAutoLayout=False)
    window.saveFileName = doc.fileName

    # run the application until exit
    app.exec()
    logger.info("Leaving app")
    pcot.config.save()
