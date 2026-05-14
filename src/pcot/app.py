"""
This is the file which creates and runs the PCOT user interface
"""
import os
from pathlib import Path

from PySide2 import QtWidgets
from PySide2.QtCore import QCommandLineParser, QCommandLineOption
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
    if sys.platform.lower().startswith('linux'):
        uid = os.getuid()
        wayland_socket = f"/run/user/{uid}/wayland-0"

        # No X11. Maybe headless, but need to check Wayland
        if not os.environ.get("DISPLAY"):
            if os.environ.get("WAYLAND_DISPLAY"):
                # Wayland but no socket; that's no good.
                if not os.path.exists(wayland_socket):
                    os.environ["QT_QPA_PLATFORM"] = "offscreen"

            # No X11 and no Wayland - definitely headless
            if not os.environ.get("WAYLAND_DISPLAY"):
                os.environ["QT_QPA_PLATFORM"] = "offscreen"

def checkApp():
    """Makes sure an app exists - we can't run certain code without one, and we often
    won't have one if we're not using a GUI. Note that the UI package also stores this
    if we are running the PCOT program."""

    setup_qt_platform()    

    global app
    if app is None:
        app = QtWidgets.QApplication()


def run(args):
    """the main function: loads any file specified, opens a mainwindow and runs its code.
    Command line parsing is done in main, which calls this."""

    global app

    # note that we don't use Qt to process the args. This is just so Qt could
    # potentially use its internal arguments.
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationVersion(pcot.__fullversion__)  # this comes from the VERSION.txt file
    app.setApplicationName("PCOT")
    app.setOrganizationName('Aberystwyth University')
    app.setOrganizationDomain('aber.ac.uk')
    pcot.ui.setApp(app)

    pcot.config.main_app_running = True
    pcot.setup()

    # create a document either ab initio or from a file, depending on args and config.
    if args.file is not None:
        path = Path(args.file)
        if not path.is_file() or path.suffix != ".pcot":
            logger.error(f"'{args.file}' is not a PCOT file or subcommand - type 'pcot -h' for help")
            sys.exit(1)
        else:
            doc = Document(args.file)
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
    app.exec_()
    logger.info("Leaving app")
    pcot.config.save()
