"""Generating help text from docstrings and connection data in XForms. Help stuff for expr nodes functions is
handled elsewhere. This is used to both generate in-app HTML and Markdown for other help data. We generate
Markdown, and then use the Markdown library to convert to HTML.
"""

from pcot.utils.table import Table
from pcot.xform import XFormException

import markdown

MDinstance = markdown.Markdown(extensions=['tables'])


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
        t.newRow()
        for i in range(0, len(xt.inputConnectors)):
            n, tp, desc = xt.inputConnectors[i]
            t.add('Index', i)
            t.add('Name', "(none)" if n == "" else n)
            t.add('Type', tp.name)
            t.add('Desc', "(none)" if desc == "" else desc)
        s += t.markdown() + '\n\n'

    if len(xt.outputConnectors) > 0:
        s += '\n### Outputs\n'
        t = Table()
        t.newRow()
        for i in range(0, len(xt.outputConnectors)):
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
