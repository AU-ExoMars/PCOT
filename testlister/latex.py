from processor import Processor

def proc(s):
    s = s.replace("_","\_").replace("$","\$")
    if len(s.strip())==0:
        s="{\\color{red}MISSING}"
    return s
    

class LatexProcessor(Processor):
    def __init__(self):
        super().__init__()
        self.intable = False
        self.table = []
       
    def closetable(self):
        if self.intable:
            for name,docstring in self.table:
                print(f"\\paragraph{{{name}}}")
                print(r"\begin{adjustwidth}{1cm}{}")
                print(docstring)
                print(r"\end{adjustwidth}") 
            self.table = []

    def opentable(self):
        if not self.intable:
            self.intable=True
            
    def end(self):
        self.closetable()
        
                

    def package(self,name,docstring):
        name = proc(name)
        docstring = proc(docstring)
        self.closetable()
        print(f"\\section{{Package {name}}}")
        print(docstring+"\n")

    def module(self,name,docstring):
        name = proc(name)
        docstring = proc(docstring)
        self.closetable()
        print(f"\\subsection{{Module {name}}}")
        print(docstring+"\n")

    def function(self,name,docstring):
        name = proc(name)
        docstring = proc(docstring)
        self.opentable()
        self.table.append((name,docstring))

    def unit_test_case(self,name,docstring):
        name = proc(name)
        docstring = proc(docstring)
        self.closetable()
        print(f"\\subsubsection{{Test Class {name}}}")
        print(docstring+"\n")

    def test_case_func(self,name,docstring):
        name = proc(name)
        docstring = proc(docstring)
        self.opentable()
        self.table.append((name,docstring))

LatexProcessor().run()
