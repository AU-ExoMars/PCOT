from typing import Optional

from .inputmethod import InputMethod
from pcot.ui.inputs import PlaceholderMethodWidget
from ..datum import Datum
from ..imagecube import ImageCube


class DirectInputMethod(InputMethod):
    """the direct method, which lets script authors get an ImageCube into the graph.
    Not accessible via the GUI"""

    img: Optional[ImageCube]

    def __init__(self, inp):
        super().__init__(inp)
        self.img = None

    def setImageCube(self, img: ImageCube):
        """Use this to set the input"""
        self.img = img

    def readData(self):
        """return the image"""
        return Datum(Datum.IMG, self.img)

    def get(self):
        """This overrides the caching method in Input; there's no point here"""
        return self.readData()

    def getName(self):
        return "Direct"

    def createWidget(self):
        return None  # returns None, which stops a button being created in the UI

    def serialise(self, internal):
        if self.img is not None:
            img = self.img.serialise()
        else:
            img = None
        return {'img': img}

    def deserialise(self, data, internal):
        if data['img'] is not None:
            self.img = ImageCube.deserialise(data['img'], self.input.mgr.doc)
        else:
            self.img = None

    def brief(self):
        if self.img is not None:
            return f"direct: {self.img.w}x{self.img.h}x{self.img.channels}"
        else:
            return "direct:none"

    def long(self):
        if self.img is not None:
            return f"direct: {str(self.img)}"
        else:
            return "direct:none"
