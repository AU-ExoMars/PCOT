## This package manages "operation functions" : these are functions which take a subimage (i.e. bounding box around an
# ROI and mask data) and some other optional data, and return an ImageCube. They can be used three ways:
# as an XForm node, as a function in an eval node, and as a plain Python function.
from typing import Callable, Dict, Any, Optional, Tuple


import numpy as np

from pcot.config import parserhook
import pcot.operations.norm
import pcot.operations.curve
from pcot.expressions import Parameter
from pcot.imagecube import SubImageCube
from pcot.xform import XForm
from pcot.datum import Datum


## This is the function which allows XForm nodes to use operation functions.
## takes an image and performs a function on it; use from the perform method of an XForm.
# The image is assumed to be input 0 of the node.
# The function takes the subimage, and should only perform the operation on the subimage.
# It also passes the kwargs into the function - this is how extra parameters get in.
# Other assumptions - node.img and node.mapping are used to output and RGBmap the image,
# image is output on connection 0.
# See norm.py, xformnorm.py for example.

def performOp(node: XForm,
              fn: Callable[[SubImageCube, Dict[str, Any]],
                Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]],
              **kwargs):
    """
    Arguments: node (this is always used as a node)
    fn: the function we call to perform the op - its args are
        the subimage we are operating on with ROI mask constructed
        dict of kwargs passed into performOp
        return value from this func is a (nominal, uncertainty, dq) triple. I could use Value, but None should
         be permitted these are pasted back into the image to form a result.
    kwargs: other args are passed as a dict into the fn
    """

    # get input 0 (the image)
    img = node.getInput(0, Datum.IMG)
    # if it's None then the input isn't connected; just output None
    if img is None:
        node.img = None
    elif not node.enabled:
        # if the node isn't enabled,  just output the input image
        node.img = img
    else:
        # otherwise the SubImageCube object from the image - this is the image clipped to
        # a BB around the ROI, with a mask for which pixels are in the ROI.
        subimage = img.copy().subimage()  # make a copy (need to do this to avoid overwriting the source).

        # perform our function, returning a Value which is a modified clipped image, uncertainty and dq.
        # We also pass the kwargs, expanding them first - optional
        # data goes here (e.g. norm() has a "mode" setting).
        result_nom, result_unc, result_dq = fn(subimage, **kwargs)

        # splice the returned clipped image into the main image, producing a new image, and
        # store it in the node
        node.img = img.modifyWithSub(subimage, result_nom, uncertainty=result_unc, dqv=result_dq)

    if node.img is not None:
        # if there's an image stored in the node, set the image's RGB mapping to be the node's
        # primary mapping (the default one)
        node.img.setMapping(node.mapping)

    # output the current value of node.img
    node.setOutput(0, Datum(Datum.IMG, node.img))



