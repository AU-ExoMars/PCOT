"""
This is the file which creates and runs the PCOT user interface
"""
import os

from PySide2 import QtWidgets
from PySide2.QtCore import QCommandLineParser, QCommandLineOption
import sys

import pcot.config
import pcot.ui.mainwindow
from pcot.document import Document
from pcot.ui import collapser
import logging

logger = logging.getLogger(__name__)

app = None


def checkApp():
    """Makes sure an app exists - we can't run certain code without one, and we often
    won't have one if we're not using a GUI. Note that the UI package also stores this
    if we are running the PCOT program."""
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

    pcot.setup()

    # create a document either ab initio or from a file, depending on args and config.
    if args.file is not None:
        doc = Document(args.file)
    else:
        loadfile = pcot.config.getDef('loadFile', fallback="")
        if loadfile != "":
            doc = Document(os.path.expanduser(loadfile))
        else:
            doc = Document()

    # Create an instance of a main window on that document
    # Autolayout not done by default - the user might have arranged things how they like.
    window = pcot.ui.mainwindow.MainUI(doc, doAutoLayout=False)
    window.saveFileName = doc.fileName

    # run the application until exit
    app.exec_()
    logger.info("Leaving app")
    pcot.config.save()
