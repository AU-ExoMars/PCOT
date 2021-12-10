"""Generating help text"""
from pcot import xform
from pcot.xform import XFormException

TABLEHEADERATTRS = 'width="100" align="left"'
TABLEROWATTRS = 'width="100" align="left"'


def HTMLtablerow(lst, tag, attrs=""):
    """helper for HTML table rows - takes a list of strings and generates a table row."""
    s = '<tr>' + ''.join(['<{}>{}</{}>'.format(tag + ' ' + attrs, x, tag) for x in lst]) + '</tr>'
    #    print(s)
    return s


def getHelpHTML(xt, errorState: XFormException):
    """generate full help for in-app HTML display given an XFormType and any error message"""

    if xt.__doc__ is None:
        s = '<font color="red">No help text is available</font>'
    else:
        s = xt.__doc__.replace('\n', '<br>')  # basic help

    s = s.replace(" ", "&nbsp;")  # need this so spacing works!

    # add connection data
    if len(xt.inputConnectors) > 0:
        s += '<br><br><font color="blue">Inputs</font><br>'
        s += '<table>'
        s += HTMLtablerow(['Index', 'Name', 'Type', 'Description'], 'th', attrs=TABLEHEADERATTRS)
        for i in range(0, len(xt.inputConnectors)):
            n, t, desc = xt.inputConnectors[i]
            s += HTMLtablerow([i, n, t, desc], 'td', attrs=TABLEROWATTRS)
        s += '</table><br>'

    if len(xt.outputConnectors) > 0:
        s += '<br><br><font color="blue">Outputs</font><br>'
        s += '<table>'
        s += HTMLtablerow(['Index', 'Name', 'Type', 'Description'], 'th', attrs=TABLEHEADERATTRS)
        for i in range(0, len(xt.outputConnectors)):
            n, t, desc = xt.outputConnectors[i]
            if n == "":
                n = "(none)"
            if desc == "":
                desc = "(none)"
            s += HTMLtablerow([i, n, t, desc], 'td', attrs=TABLEROWATTRS)
        s += '</table><br>'

    if errorState is not None:
        s += '<br><font color="red">ERROR:<br>' + errorState.code + '<br>' + errorState.message + '</font>'
    return s


def getHelpMarkdown(xt):
    """generate Markdown help given an XFormType"""

    if xt.__doc__ is None:
        s = 'No help text is available\n'
    else:
        s = xt.__doc__ + '\n'

    # trim tabs
    s = "\n".join([x.strip() for x in s.split('\n')])+"\n\n"

    # add connection data
    if len(xt.inputConnectors) > 0:
        s += '##Inputs\n'
        s += MDtablerow(['Index', 'Name', 'Type', 'Description'], True)
        for i in range(0, len(xt.inputConnectors)):
            n, t, desc = xt.inputConnectors[i]
            s += MDtablerow([i, n, t, desc])
        s += '\n\n'

    if len(xt.outputConnectors) > 0:
        s += '##Outputs\n'
        s += MDtablerow(['Index', 'Name', 'Type', 'Description'], True)
        for i in range(0, len(xt.outputConnectors)):
            n, t, desc = xt.outputConnectors[i]
            if n == "":
                n = "(none)"
            if desc == "":
                desc = "(none)"
            s += MDtablerow([i, n, t, desc])
        s += '\n\n'

    return s

def MDtablerow(lst, isHeader=False):
    s = "|" + ("|".join([str(x) for x in lst])) + "|\n"
    if isHeader:
        s += "|" + ("|".join(['-----' for _ in lst])) + "|\n"
    return s



def markdownHelpAllXForms():
    s = ""
    for name, x in xform.allTypes.items():
        s += f"# {name}\n\n"
        s += getHelpMarkdown(x) + "\n\n"

    return s

def generateHelpFiles():
    # this is currently fixed to a test directory.
    with open("/home/white/testpcotdocs/docs/docs.md","w") as f:
        f.write(markdownHelpAllXForms())



