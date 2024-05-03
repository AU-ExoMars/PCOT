from pcot.imagecube import ImageCube
from pcot.datum import Datum
from pcot.datumtypes import Type
from pcot.expressions.register import datumfunc

from pcot.expressions.ops import combineImageWithNumberSources



# The first part of the plugin creates a new type of node.

# this decorator will cause the node to auto-register.

@datumfunc
def dqset(img,bits):
    """
    sets DQ bits
    @param img:img:the image
    @param bits:number:the bit mask to set
    """
    inimg = img.get(Datum.IMG)  # get the first argument
    bits = bits.get(Datum.NUMBER)  # and the second argument.

    s = inimg.subimage()
    out = inimg.modifyWithSub(s, None, dqOR=int(bits.n))

    out.rois = inimg.rois.copy()
    out.sources = combineImageWithNumberSources(inimg, out.getSources())
    return Datum(Datum.IMG, out)
