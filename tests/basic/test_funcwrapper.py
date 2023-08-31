"""
Test the functions which are wrapped with funcWrapper. Some testing is also done in graphs to test the ordering
"""

import pcot
from fixtures import genrgb
from pcot.document import Document
from pcot.value import Value


def scalar_core(expr: str, inp: Value, expected: Value):
    pcot.setup()
    doc = Document()

    i = doc.graph.create("expr")
    i.expr = "v("

    e = doc.graph.create("expr")
    e.expr = expr





