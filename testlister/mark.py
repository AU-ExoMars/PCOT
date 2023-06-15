from processor import Processor
from markdown import Markdown

def proc(s,latex=True):
    if len(s.strip())==0:
        s="**MISSING**"
    return s
    

class MarkdownProcessor(Processor):
    def __init__(self):
        super().__init__()
        
                

    def package(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        out+=f"# Package {name}\n\n"
        out+=docstring+"\n"
        return out

    def module(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        out+=f"## Module {name}\n\n"
        out+=docstring+"\n"
        return out

    def function(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        out+=f"### Function {name}\n\n"
        out+=docstring+"\n"
        return out
        

    def unit_test_case(self,name,docstring):
        out = ""
        name = proc(name)
        docstring = proc(docstring)
        out+=f"## Test Class {name}\n\n"
        out+=docstring+"\n"
        return out

    def test_case_func(self,name,docstring):
        return self.function(name,docstring)

s=MarkdownProcessor().run()
print(Markdown().convert(s))
