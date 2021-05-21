from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QPlainTextEdit, QTextEdit

from pcot import ui
from pcot.xform import allTypes


def handleMenuEvent(self, ev):
    # get work under mouse cursor
    tc = self.cursorForPosition(ev.pos())
    tc.select(QTextCursor.WordUnderCursor)
    funcname = tc.selectedText()
    menu = self.createStandardContextMenu()

    lfact = menu.addAction("List all functions")

    fhact = "dummy"
    if len(funcname) > 0:
        fhact = menu.addAction("Get help on '{}'".format(funcname))
    else:
        a = menu.addAction("Hover over a function name and right-click for help")
        a.setDisabled(True)
        menu.addAction(a)

    parser = allTypes['eval'].parser    # the eval node type owns the parser, which knows about funcs.

    a = menu.exec_(ev.globalPos())
    if a == fhact:
        txt = "<h1>Help on {}</h1>".format(funcname)
        txt += parser.funcHelp(funcname)
        ui.log(txt)
    elif a == lfact:
        txt = "<h1>List of all functions in eval node</h1>"
        txt += parser.listFuncs()
        ui.log(txt)
    else:
        menu.exec_(ev.globalPos())


class PlainTextEditWithHelp(QPlainTextEdit):
    def __init__(self, parent):
        super().__init__(parent)

    def contextMenuEvent(self, ev):
        handleMenuEvent(self, ev)


class TextEditWithHelp(QTextEdit):
    def __init__(self, parent):
        super().__init__(parent)

    def contextMenuEvent(self, ev):
        handleMenuEvent(self, ev)
