from pcot.datum import Datum
from pcot.inputs.envimethod import ENVIInputMethod

from pcot.rois import ROICircle
from pcot.utils.spectrum import SpectrumSet
from fixtures import *


def test_direct_input(envi_image_1):
    """Test direct input of an image cube, but not from a PNG file"""

    # try to load an image by constructing an input method object, setting its parameters

    # create a new input method object, set the file name and load the item
    datum = ENVIInputMethod(None).setFileName(envi_image_1).get()
    # get the image from the datum
    img = datum.get(Datum.IMG)

    # add a couple of circular ROIs to the image
    img.rois.append(ROICircle(50, 40, 4, label="a"))
    img.rois.append(ROICircle(8, 8, 4, label="b"))

    # generate a spectrum set and convert the results to a CSV table
    ss = SpectrumSet({"in": img}).table().html()
    # print
    print(ss)



