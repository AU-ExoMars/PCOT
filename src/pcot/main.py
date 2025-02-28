# The main function with command line parsing, setting up the UI.
# Run from both __main__ and from the "pcot" entry point script.
import logging
import os
import sys
import importlib

from PySide2 import QtWidgets
from PySide2.QtCore import QCommandLineParser, QCommandLineOption

import pcot.config
import pcot.ui.mainwindow
from pcot.document import Document
from pcot.ui import collapser

app = None

logger = logging.getLogger(__name__)

try:
    import pyi_splash

    # Update the text on the splash screen
    pyi_splash.update_text("PCOT loaded.")
    pyi_splash.update_text("And PCOT still loaded.")

    # Close the splash screen. It does not matter when the call
    # to this function is made, the splash screen remains open until
    # this function is called or the Python program is terminated.
    pyi_splash.close()
except ImportError as e:
    pass


def checkApp():
    """Makes sure an app exists - we can't run certain code without one, and we often
    won't have one if we're not using a GUI. Note that the UI package also stores this
    if we are running the PCOT program."""
    global app
    if app is None:
        app = QtWidgets.QApplication()


def main():
    """the main function: parses command line, loads any files specified,
    opens a mainwindow and runs its code."""
    global app

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationVersion(pcot.__fullversion__)  # this comes from the VERSION.txt file
    app.setApplicationName("PCOT")
    app.setOrganizationName('Aberystwyth University')
    app.setOrganizationDomain('aber.ac.uk')
    pcot.ui.setApp(app)

    parser = QCommandLineParser()
    parser.addHelpOption()
    parser.addVersionOption()
    parser.addPositionalArgument("file", "A PCOT document to open")
    logopt = QCommandLineOption(["l", "log"], "set debugging level", "loglevel", defaultValue="info")
    parser.addOption(logopt)

    parser.process(app)
    args = parser.positionalArguments()

    log = parser.value(logopt)
    logger.setLevel(log.upper())

    pcot.setup()

    # create a document either ab initio or from a file, depending on args and config.
    if len(args) > 0:
        doc = Document(args[0])
    else:
        loadfile = pcot.config.getDef('loadFile', fallback=None)
        if loadfile is not None:
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


if __name__ == "__main__":
    main()
