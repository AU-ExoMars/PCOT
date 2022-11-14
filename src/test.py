import pcot
from pcot.document import Document
from pcot.imageexport import exportPDF, exportSVG, exportRaster
from pcot.xforms.xformgrad import LEFT_MARGIN

pcot.setup()
d = Document("c:/users/jim/pcot/mkdocs/docs/gettingstarted/671438grad.pcot")
# then we tell it the graph has changed, and it will run.
node = d.getNodeByName("gradient")
node.legendPos = LEFT_MARGIN
d.changed()

img = node.getOutput(0)
# and write to a PDF
exportRaster(img, "c:/users/jim/pictures/zz.png")
exportPDF(img, "c:/users/jim/pictures/zz.pdf")
exportSVG(img, "c:/users/jim/pictures/zz.svg")
