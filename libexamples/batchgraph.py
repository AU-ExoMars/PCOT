
# This example opens a graph, process some ENVI files through that graph,
# and saves them back to an ENVI.


import pcot
from pcot.document import Document
from pcot.datum import Datum
from pcot.dataformats import envi

# initialise PCOT
pcot.setup()

# load the document
doc = Document("1.pcot")

# run the graph for some ENVI files. We'll just do one here.

for file in ("1",):

    # load the given ENVI file into input 0
    rv = doc.setInputENVI(0, f"../exampleData/{file}.hdr")
    if rv is not None:
        raise Exception(f"{rv}")

    # run the graph by telling the document it has changed
    doc.run()

    # get the "sink" node
    outNode = doc.getNodeByName("sink")
    
    # get its output
    img = outNode.data.get(Datum.IMG)
    print(f"Image size: {img.w} x {img.h} x {img.channels}");
 
    # write to new ENVI, e.g. 1b.hdr
    envi.write(file+"b",img)
