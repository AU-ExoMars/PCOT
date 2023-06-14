import pytest
import sys
import re
from io import StringIO

class Processor():
    def package(self,name,docstring):
        pass
    def module(self,name,docstring):
        pass
    def function(self,name,docstring):
        pass

    def unit_test_case(self,name,docstring):
        pass
    def test_case_func(self,name,docstring):
        pass
        
    def end(self):
        pass
        
    def __init__(self):
        pass

    def fetch(self):
        old = sys.stdout
        sys.stdout = StringIO()

        pytest.main(['--co','--verbose','..'])

        self.data = sys.stdout.getvalue()
        sys.stdout.close()
        sys.stdout = old
        
    
    def process_previous_text(self,tp,name,docstring):
        if name is None or tp is None:
            return
        if tp == "Package":
            self.package(name,docstring)
        elif tp == "Module":
            self.module(name,docstring)
        elif tp == "Function":
            self.function(name,docstring)
        elif tp == "UnitTestCase":
            self.unit_test_case(name,docstring)
        elif tp == "TestCaseFunction":
            self.test_case_func(name,docstring)
        else:
            raise Exception(f"unknown {tp}")
            

    def process(self):
        table = str.maketrans('','','<>')
        docstring = ""
        name = None
        tp = None
        
        for s in self.data.split('\n'):
            s = s.strip()
            if not s.startswith("====="):
                if s.startswith("<"):
                    self.process_previous_text(tp,name,docstring.strip())
                    tp,name = s.translate(table).split()
                    docstring = ""
                else:
                    docstring += s+"\n"
                
        self.process_previous_text(tp,name,docstring)


    def run(self):
        self.fetch()
        self.process()
        self.end()

