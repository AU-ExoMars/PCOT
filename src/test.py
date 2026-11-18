from glob import glob

import pcot
from pcot.datum import Datum
from pcot.document import Document
from pcot.imagecube import ImageCube
from utils.table import Table

# initialise PCOT
pcot.setup()

# create and load the document which will process the data
doc = Document("c:/users/jcf12/PCOT/harry.pcot")

# get a reference to the "sink" node (which is in the document's graph and holds the final output)
sink = doc.getNodeByName("sink")
circ = doc.getNodeByName("circle-cal")
circ.params.croi.x = 300
circ.params.croi.y = 300
circ.params.croi.r = 19

print(circ)

# set input 0 to hold the data you are processing
files = glob("C:/Users/jimfi/Downloads/Agt_stromatolite_JF/Agt_stromatolite_JF/*.png")
print(files)
doc.setInputMulti(inputidx=0, directory="C:/Users/jimfi/Downloads/Agt_stromatolite_JF/Agt_stromatolite_JF",
    fnames=["260213_133702_Training Model-R01_+242_03.601s.png",
        "260213_134038_Training Model-R02_+250_02.601s.png",
        "260213_134419_Training Model-R03_+257_02.301s.png",
        "260213_134710_Training Model-R04_+259_02.001s.png",
        "260213_135137_Training Model-R05_+260_01.301s.png"],
       filterpat=r".*Model-(?P<lens>L|R)(?P<n>[0-9][0-9]).*",camera="TRAINING_GEOLOGY")

# run the document!
doc.run()

# get the data field in the sink node (all sinks have this)
out = sink.data

# turn that Datum object into an table
t:Table = out.get(Datum.TABLE)

print(t.text())