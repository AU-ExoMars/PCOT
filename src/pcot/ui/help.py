"""Generating help text from docstrings and connection data in XForms. Help stuff for expr nodes functions is
handled elsewhere. This is used to both generate in-app HTML and Markdown for other help data. We generate
Markdown, and then use the Markdown library to convert to HTML.
"""
import logging

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

import pcot
from pcot.utils.table import Table
from pcot.xform import XFormException

import markdown

logger = logging.getLogger(__name__)

# have to give the FULL package name for each extension so that PyInstaller can work. They also
# need to be added to the hidden imports.

MDinstance = markdown.Markdown(extensions=['markdown.extensions.tables'])


def markdownWrapper(s):
    """This will not be thread-safe if we are only using a single markdown instance."""
    MDinstance.reset()
    out = MDinstance.convert(s)
    return out


def getHelpMarkdown(xt, errorState: XFormException = None, inApp=False):
    """generate Markdown help for both converting into in-app HTML display and
     generating external help files, given an XFormType and any error message. If inApp is true,
     the formatting may be slightly different."""

    if xt.__doc__ is None:
        h = '**No help text is available**'
    else:
        h = xt.__doc__  # help doc comes from docstring

    # docstrings have whitespace at starts of lines.
    h = "\n".join([x.strip() for x in h.split('\n')])

    h = markdownWrapper(h)
    s = f"# {xt.name}\n\n## Description\n\n{h}\n\n*****\n\n## Connections\n\n"

    # add connection data

    if len(xt.inputConnectors) > 0:
        s += '\n### Inputs\n'
        t = Table()
        for i in range(0, len(xt.inputConnectors)):
            t.newRow()
            n, tp, desc = xt.inputConnectors[i]
            t.add('Index', i)
            t.add('Name', "(none)" if n == "" else n)
            t.add('Type', tp.name)
            t.add('Desc', "(none)" if desc == "" else desc)
        s += t.markdown() + '\n\n'

    if len(xt.outputConnectors) > 0:
        s += '\n### Outputs\n'
        t = Table()
        for i in range(0, len(xt.outputConnectors)):
            t.newRow()
            n, tp, desc = xt.outputConnectors[i]
            t.add('Index', i)
            t.add('Name', "(none)" if n == "" else n)
            t.add('Type', tp.name)
            t.add('Desc', "(none)" if desc == "" else desc)
        s += t.markdown() + '\n\n'

    if errorState is not None:
        s += f"# ERROR: [{errorState.code}] {errorState.message}"
    return s


def getHelpHTML(xt, errorState: XFormException = None):
    s = getHelpMarkdown(xt, errorState, inApp=True)
    return markdownWrapper(s)


class HelpWindow(QtWidgets.QDialog):
    def __init__(self, parent, tp=None, md=None, title=None, node=None):
        """Either node or md should be set.
        - tp: the text for the given node type will be shown; title is ignored
        - md: the markdown will converted to HTML and shown; title should be assigned too.
        - node: if this is present, a particular node's error will be shown if there is one"""
        super().__init__(parent=parent)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        layout = QtWidgets.QVBoxLayout(self)
        if tp is not None:
            tp.helpwin = self
            txt = getHelpHTML(tp, node.error if node is not None else None)
            self.setWindowTitle(f"Help for '{tp.name}'")
        elif md is not None:
            txt = markdownWrapper(md)
            self.setWindowTitle("Help" if title is None else title)
        else:
            txt = "<h1>Bad help!</h1><p>No markdown or node type provided</p>"
            logger.error("Bad help - no markdown or node type provided")
        wid = QtWidgets.QTextEdit()
        wid.setReadOnly(True)
        font = QFont("Consolas")
        font.setPixelSize(15)
        wid.setFont(font)
        wid.setMinimumSize(800, 500)
        wid.document().setDefaultStyleSheet(pcot.ui.textedit.styleSheet)
        #  wid.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        wid.setText(txt)
        layout.addWidget(wid)

        #        button = QtWidgets.QPushButton("Close")
        #        button.clicked.connect(lambda: self.close())
        #        layout.addWidget(button)

        self.show()



