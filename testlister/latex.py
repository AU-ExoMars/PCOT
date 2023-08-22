import markdown

from md2latex import LaTeXExtension
from processor import Processor
md = markdown.Markdown()
md2l = LaTeXExtension()
md2l.extendMarkdown(md)


def markdown2latex(s):
    s = md.convert(s)
    # strip out the root node stuff
    return s.replace("<root>","").replace("</root>","").strip()


def proc(s,latex=True):
    if latex:
        s = s.replace("__","SNARKDUNDER")
    if len(s.strip())==0:
        s="{\\color{red}MISSING}"
    elif latex:
        s = markdown2latex(s)
        s = s.replace("SNARKDUNDER","__")
    s = s.replace("_","\_")
    s = s.replace("$","\$")
    return s
    

class LatexProcessor(Processor):
    def __init__(self, opts):
        super().__init__(opts)

    def preamble(self, text):
        self.add("\\section{Introduction}\n"+text+'\n\n\n')

    def package(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        out+=f"\\section{{Package {name}}}"
        out+=docstring+"\n"
        return out

    def module(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        out+=f"\\subsection{{Module {name}}}"
        out+=docstring+"\n"
        return out

    def function(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        out+=f"\\paragraph{{{name}}}"
        out+=r"\begin{adjustwidth}{1cm}{}"
        out+=docstring
        out+=r"\end{adjustwidth}"+"\n"
        return out
        
    def graph(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        out+=f"\\paragraph{{Graph {name}}}"
        out+=r"\begin{adjustwidth}{1cm}{}"
        out+=docstring
        out+=r"\end{adjustwidth}"+"\n"
        return out

    def unit_test_case(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        out+=f"\\subsubsection{{Test Class {name}}}"
        out+=docstring+"\n"
        return out

    def test_case_func(self,name,docstring):
        return self.function(name,docstring)
