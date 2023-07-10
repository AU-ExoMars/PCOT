from processor import Processor
from markdown import Markdown

def proc(s,latex=True):
    if len(s.strip())==0:
        s="**MISSING**"
    return s
    

class MarkdownProcessor(Processor):
    def __init__(self,opts,convert_to_html):
        super().__init__(opts)
        self.convert_to_html = convert_to_html
        self.curpack = ''
        self.curmod = ''
        self.curclass = ''
        self.fullname = opts['fullname']
        
    def preamble(self, text):
        self.add("# Introduction\n"+text+'\n\n\n')
        
    def package(self,name,docstring):
        out = ""
        name = proc(name)
        self.curpack = name
        docstring = proc(docstring)
        out+=f"# Package {name}\n\n"
        out+=docstring+"\n\n"
        return out

    def module(self,name,docstring):
        out = ""
        name = proc(name)
        self.curmod = name
        docstring = proc(docstring)
        if self.fullname:
            out+=f"## Module {self.curpack}/{name}\n\n"
        else:
            out+=f"## Module {name}\n\n"
        out+=docstring+"\n\n"
        return out

    def function(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        if self.fullname:
            out+=f"### Function {self.curpack}/{self.curmod}/{name}\n\n"
        else:
            out+=f"### Function {name}\n\n"
        out+=docstring+"\n\n"
        return out
        

    def unit_test_case(self,name,docstring):
        out = ""
        name = proc(name)
        self.curclass = name
        docstring = proc(docstring)
        if self.fullname:
            out+=f"### Test Class {self.curpack}/{self.curmod}/{name}\n\n"
        else:
            out+=f"## Test Class {name}\n\n"
        out+=docstring+"\n\n"
        return out

    def test_case_func(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        if self.fullname:
            out+=f"### Method {self.curpack}/{self.curmod}/{self.curclass}:{name}\n\n"
        else:
            out+=f"### Method {name}\n\n"
        out+=docstring+"\n\n"
        return out

    def run(self):
        s = super().run()
        if self.convert_to_html:
            return Markdown().convert(s)
        else:
            return s
