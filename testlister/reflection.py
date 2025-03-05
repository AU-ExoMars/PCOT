import pcot
from pcot.document import Document

def getdocstring(graphname):
    doc = Document(graphname)
    ns = doc.graph.getByDisplayName("comment")
    for n in ns:
        if n.string.startswith("DOC"):
            return n.string[3:].strip()
    return "No documentation found in .pcot file. This should be in a comment node and start with DOC"
