# The main function with command line parsing, setting up the UI.
# Run from both __main__ and from the "pcot" entry point script.

from PyQt5 import QtWidgets
from PyQt5.QtCore import QCommandLineParser
import os, sys

from pcot import config, ui
import pcot.ui.mainwindow


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

    window = pcot.ui.mainwindow.MainUI()  # Create an instance of a main window
    if len(args) > 0:
        window.load(args[0])
    else:
        loadfile = config.get('Default', 'loadFile', fallback=None)
        if loadfile is not None:
            window.load(os.path.expanduser(loadfile))

    app.exec_()  # Start the application


if __name__ == "__main__":
    main()
