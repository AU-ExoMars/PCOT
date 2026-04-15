import pcot
from pcot.datum import Datum
from pcot.document import Document
from pcot.imagecube import ImageCube

# initialise PCOT
pcot.setup()

# create and load the document which will process the data
doc = Document()
doc.load("holly_process.pcot")

# get a reference to the "sink" node (which is in the document's graph and holds the final output)
sink = doc.getNodeByName("sink")

# set input 0 to hold the data you are processing
doc.setInputMulti(inputidx=0, directory="C:/Users/jimfi/Downloads/Agt_stromatolite_JF/Agt_stromatolite_JF",
    fnames=["260213_133702_Training Model-R01_+242_03.601s.png",
        "260213_134038_Training Model-R02_+250_02.601s.png",
        "260213_134419_Training Model-R03_+257_02.301s.png",
        "260213_134710_Training Model-R04_+259_02.001s.png",
        "260213_135137_Training Model-R05_+260_01.301s.png"],
       filterpat=r".*Model-(?P<lens>L|R)(?P<n>[0-9][0-9]).*",camname="TRAINING_GEOLOGY")

# run the document!
doc.run()

# get the data field in the sink node (all sinks have this)
out = sink.data

# turn that Datum object into an image (returns null if it isn't an image or there's nothing there)
img:ImageCube = out.get(Datum.IMG)

# save the image, using the RGB mapping specified in the "sink" node.
img.save("output.png", annotations=False)

## you can repeatedly do setInputMulti,run,get and save data ...
