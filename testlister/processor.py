import pytest
import sys
import re

from io import StringIO
import logging

logger = logging.getLogger(__name__)

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
        
    def preamble(self, text):
        pass
        
    def end(self):
        pass
        
    def __init__(self, opts):
        self.text = ""

    def fetch(self):
        logger.info("Running pytest --co --verbose")
        old = sys.stdout
        sys.stdout = StringIO()

        pytest.main(['--co','--verbose','..'])

        self.data = sys.stdout.getvalue()
        sys.stdout.close()
        sys.stdout = old

    def add(self,s):
        self.text += s        
    
    def process_previous_text(self,tp,name,docstring):
        if name is None or tp is None:
            return
        if tp == "Package":
            self.add(self.package(name,docstring))
        elif tp == "Module":
            self.add(self.module(name,docstring))
        elif tp == "Function":
            self.add(self.function(name,docstring))
        elif tp == "UnitTestCase":
            self.add(self.unit_test_case(name,docstring))
        elif tp == "TestCaseFunction":
            self.add(self.test_case_func(name,docstring))
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
        return self.text

