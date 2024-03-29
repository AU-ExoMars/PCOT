# Using PCOT as a library
If you are using the source distribution of PCOT you can write Python
scripts which use PCOT components. A typical example might be a script
to read a PCOT document and run some data through that document's graph.
You could do that like this:

```python
# This example opens a graph, process some ENVI files through that graph,
# and saves them back to an ENVI. It assumes the graph has an "input 0" node
# which receives an image and a "sink" node which receives the processed
# image.

import pcot
from pcot.document import Document
from pcot.datum import Datum
from pcot.dataformats.envi import write

# initialise PCOT
pcot.setup()

# load the document
doc = Document("1.pcot")

# run the graph for some ENVI files. We'll just do one here, the ENVI
# document contained in the files 1.hdr and 1.dat (an ENVI document
# consists of two files: header and data).

for file in ("1",):

    # load the given ENVI file into input 0
    rv = doc.setInputENVI(0, file+".hdr")
    if rv is not None:
        raise Exception(f"{rv}")

    # run the graph by telling the document it has changed
    doc.changed()

    # get the "sink" node
    outNode = doc.getNodeByName("sink")
    
    # get its output
    img = outNode.out.get(Datum.IMG)
 
    # write to new ENVI, e.g. 1b.hdr
    write(file+"b",img)
```

