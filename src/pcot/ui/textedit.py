from PySide2.QtGui import QTextCursor
from PySide2.QtWidgets import QPlainTextEdit, QTextEdit

from pcot import ui
from pcot.ui.help import markdownWrapper
from pcot.xform import allTypes


def handleMenuEvent(self, ev):
    # get work under mouse cursor
    tc = self.cursorForPosition(ev.pos())
    tc.select(QTextCursor.WordUnderCursor)
    funcname = tc.selectedText()
    menu = self.createStandardContextMenu()

    lfact = menu.addAction("List all functions")
    lpact = menu.addAction("List all properties")

    fhact = "dummy"
    if len(funcname) > 0:
        fhact = menu.addAction("Get help on '{}'".format(funcname))
    else:
        a = menu.addAction("Hover over a function name and right-click for help")
        a.setDisabled(True)

    parser = allTypes['expr'].parser  # the eval node type owns the parser, which knows about funcs.

    a = menu.exec_(ev.globalPos())
    if a == fhact:
        txt = "<h1>Help on {}</h1>".format(funcname)
        txt += markdownWrapper(parser.helpOnWord(funcname))
        ui.log(txt, toStdout=False)
    elif a == lfact:
        txt = "<h1>List of all functions in eval node</h1>"
        txt += markdownWrapper(parser.listFuncs())
        ui.log(txt, toStdout=False)
    elif a == lpact:
        txt = "<h1>List of all 'x.y' properties in eval node</h1>"
        txt += markdownWrapper(parser.listProps())
        ui.log(txt, toStdout=False)
    else:
        menu.exec_(ev.globalPos())


class PlainTextEditWithHelp(QPlainTextEdit):
    def __init__(self, parent):
        super().__init__(parent)

    def contextMenuEvent(self, ev):
        handleMenuEvent(self, ev)


styleSheet = """
th, td {
    border: 1px;
    padding-bottom: 10px;
    padding-top: 5px;
    padding-left: 5px;
    padding-right: 5px;
}

td {
    border-style: solid none none none;
    background-color: #d0d0ff;
}

th {
    background-color: #8080ff;
    border-style: double;
    text-align: left;
}
"""


class TextEditWithHelp(QTextEdit):
    def __init__(self, parent):
        super().__init__(parent)
        # This isn't really clear from the docs - calling .setStyleSheet() set the style on the *widget*, not the
        # text it contains. This will set the style on the document.
        self.document().setDefaultStyleSheet(styleSheet)

    def contextMenuEvent(self, ev):
        handleMenuEvent(self, ev)
