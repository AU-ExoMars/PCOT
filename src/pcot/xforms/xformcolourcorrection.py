from typing import Optional

from pcot.colour_correction.constants import ILLUMINANTS, DEFAULT_SRC_ILLUMINANT, \
    DEFAULT_SRC_CAMERA_SCENE, COLOUR_CORRECTION_MATRICES
from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.xform import xformtype, XFormType
from pcot.xforms.tabgeneric import TabGeneric

HELP = """
**This is very much a placeholder.** Future incarnations of this node may look quite different.

* Set the camera to the required camera, and the illuminant to the best match for the scene.

* Set the illuminant to the best match for the scene - you'll probably have a little more choice
here. See the node help for more details of why there are two parameters here. 
"""

@xformtype
class XFormColourCorrect(XFormType):
    """
    A basic colour correction node - this will be improved in subsequent versions to handle
    more cameras and illuminants.

    It might seem odd that you have to select camera+illuminant, and also separately
    select the illuminant. The algorithm will sort of work with the incorrect illuminant
    in the camera+illuminant setting, but won't work well with the wrong illuminant in the second.
    Therefore we provide two separate settings in case we can't prepare colour correction matrices for all
    combinations.
    """

    def __init__(self):
        super().__init__("colourcorrect","calibration","0.0.0")
        self.addInputConnector("",Datum.IMG)
        self.addOutputConnector("",Datum.IMG)
        self.params = TaggedDictType(
            camera_and_scene=("Camera / closest scene illuminant", str,
                              # these come from constants.py
                              DEFAULT_SRC_CAMERA_SCENE,
                              list(COLOUR_CORRECTION_MATRICES.keys()),
                              ),
            illuminant=("Scene illuminant", str,
                        # these come from constants.py
                        DEFAULT_SRC_ILLUMINANT,
                        list(ILLUMINANTS.keys())
                        )
        )

    def createTab(self, xform, window):
        return TabGeneric(xform, window, help_markdown=HELP)

    def init(self, node):
        pass

    def perform(self, node):
        img: Optional[ImageCube] = node.getInput(0, Datum.IMG)
        out = None
        if img is not None:
            from pcot.colour_correction.correct import ColourCorrection
            cc = ColourCorrection(node.params.camera_and_scene, node.params.illuminant)
            outimg = cc.process(img.img)
            out = ImageCube(outimg, uncertainty=None, dq=img.dq, sources=img.sources)
            out = Datum(Datum.IMG, out)

        node.setOutput(0, out)
