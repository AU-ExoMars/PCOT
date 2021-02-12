## @package main
# The main function with command line parsing and very little else.

from PyQt5 import QtWidgets, uic, QtCore, QtGui
from PyQt5.QtCore import Qt,QCommandLineOption,QCommandLineParser
import os,sys,traceback,json,time,getpass

import ui.tabs,ui.help,ui.mainwindow
import xform
import graphview,palette,graphscene
import filters

# import all transform types (see the __init__.py there)
# ACTUALLY REQUIRED despite what the IDE says!
import xforms
from xforms import *


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
    ui.app = app
    
    parser = QCommandLineParser()
    parser.addHelpOption()
    parser.addVersionOption()
    parser.addPositionalArgument("file", "A JSON graph file to open")
    
    
    parser.process(app)
    args = parser.positionalArguments() 

    window=ui.mainwindow.MainUI() # Create an instance of a main window
    if len(args)>0:
        window.load(args[0])
    app.exec_() # Start the application
    

if __name__ == "__main__":
    main()
