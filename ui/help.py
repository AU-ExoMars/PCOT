#
# Generating help text
#

# generate full help given an XFormType
def help(xt):
    if xt.__doc__ is None:
        s= '<font color="red">No help text is available</font>'
    else:
        s = xt.__doc__.replace('\n','<br>') # basic help

    # add connection data
    if len(xt.inputConnectors)>0:
        s += '<br><br><font color="blue">Inputs</font><br>'
        s += '<table>'
        s += tablerow(['Index','Name','Type','Description'],'th')
        for i in range(0,len(xt.inputConnectors)):
            n,t,desc = xt.inputConnectors[i]
            s += tablerow([i,n,t,desc],'td')
        s += '</table><br>'

    if len(xt.outputConnectors)>0:
        s += '<br><br><font color="blue">Outputs</font><br>'
        s += '<table>'
        s += tablerow(['Index','Name','Type','Description'],'th')
        for i in range(0,len(xt.outputConnectors)):
            n,t,desc = xt.outputConnectors[i]
            s += tablerow([i,n,t,desc],'td')
        s += '</table><br>'

    return s



# helpers for HTML

def tablerow(lst,tag):
    return '<tr>'+''.join(['<{}>{}</{}>'.format(tag,x,tag) for x in lst])+'</tr>'
