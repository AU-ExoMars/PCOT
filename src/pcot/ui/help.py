## @package ui.help
# Generating help text
#

from pcot.xform import XFormException

TABLEHEADERATTRS = 'width="100" align="left"'
TABLEROWATTRS = 'width="100" align="left"'


## generate full help given an XFormType and any error message
def getHelpHTML(xt, errorState: XFormException):
    if xt.__doc__ is None:
        s = '<font color="red">No help text is available</font>'
    else:
        s = xt.__doc__.replace('\n', '<br>')  # basic help

    s = s.replace(" ", "&nbsp;")  # need this so spacing works!

    # add connection data
    if len(xt.inputConnectors) > 0:
        s += '<br><br><font color="blue">Inputs</font><br>'
        s += '<table>'
        s += tablerow(['Index', 'Name', 'Type', 'Description'], 'th', attrs=TABLEHEADERATTRS)
        for i in range(0, len(xt.inputConnectors)):
            n, t, desc = xt.inputConnectors[i]
            s += tablerow([i, n, t, desc], 'td', attrs=TABLEROWATTRS)
        s += '</table><br>'

    if len(xt.outputConnectors) > 0:
        s += '<br><br><font color="blue">Outputs</font><br>'
        s += '<table>'
        s += tablerow(['Index', 'Name', 'Type', 'Description'], 'th', attrs=TABLEHEADERATTRS)
        for i in range(0, len(xt.outputConnectors)):
            n, t, desc = xt.outputConnectors[i]
            if n == "":
                n = "(none)"
            if desc == "":
                desc = "(none)"
            s += tablerow([i, n, t, desc], 'td', attrs=TABLEROWATTRS)
        s += '</table><br>'

    if errorState is not None:
        s += '<br><font color="red">ERROR:<br>' + errorState.code + '<br>' + errorState.message + '</font>'
    return s


## helper for HTML table rows - takes a list of strings and generates a table row.
def tablerow(lst, tag, attrs=""):
    s = '<tr>' + ''.join(['<{}>{}</{}>'.format(tag+' '+attrs, x, tag) for x in lst]) + '</tr>'
#    print(s)
    return s
