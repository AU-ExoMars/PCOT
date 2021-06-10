# The main function with command line parsing, setting up the UI.
# Run from both __main__ and from the "pcot" entry point script.

from PyQt5 import QtWidgets
from PyQt5.QtCore import QCommandLineParser
import os, sys

import pcot.config
import pcot.ui.mainwindow
from pcot.document import Document

app = None


## the main function: parses command line, loads any files specified,
# opens a mainwindow and runs its code.

def main():
    global app

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationVersion("0.0.0")
    app.setApplicationName("PCOT")
    app.setOrganizationName('Aberystwyth University')
    app.setOrganizationDomain('aber.ac.uk')
    pcot.ui.setApp(app)

    parser = QCommandLineParser()
    parser.addHelpOption()
    parser.addVersionOption()
    parser.addPositionalArgument("file", "A JSON graph file to open")

    parser.process(app)
    args = parser.positionalArguments()

    if len(args) > 0:
        doc = Document(args[0])
    else:
        loadfile = pcot.config.default.get('loadFile', fallback=None)
        if loadfile is not None:
            doc = Document(os.path.expanduser(loadfile))
        else:
            doc = Document()

    window = pcot.ui.mainwindow.MainUI(doc=doc, doAutoLayout=True)  # Create an instance of a main window
    app.exec_()  # Start the application
    print("Leaving app")
    pcot.config.save()


if __name__ == "__main__":
    main()
