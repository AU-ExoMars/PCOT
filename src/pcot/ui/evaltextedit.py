from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QPlainTextEdit

from pcot import ui


class EvalTextEdit(QPlainTextEdit):
    def __init__(self, parent):
        super().__init__(parent)

    def contextMenuEvent(self, ev):
        # get work under mouse cursor
        tc = self.cursorForPosition(ev.pos())
        tc.select(QTextCursor.WordUnderCursor)
        funcname = tc.selectedText()
        menu = self.createStandardContextMenu()

        lfact = menu.addAction("List all functions")

        fhact = "dummy"
        if len(funcname) > 0:
            fhact = menu.addAction("Get help on '{}'".format(funcname))

        a = menu.exec_(ev.globalPos())
        if a == fhact:
            txt = "<h1>Help on {}</h1>".format(funcname)
            txt += self.node.type.parser.funcHelp(funcname)
            ui.log(txt)
        elif a == lfact:
            txt = "<h1>List of all functions in eval node</h1>"
            txt += self.node.type.parser.listFuncs()
            ui.log(txt)
        else:
            menu.exec_(ev.globalPos())
