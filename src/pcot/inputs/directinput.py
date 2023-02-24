from typing import Optional

from .inputmethod import InputMethod
from ..datum import Datum
from ..imagecube import ImageCube


class DirectInputMethod(InputMethod):
    """the direct method, which lets script authors get an ImageCube into the graph.
    Not accessible via the GUI"""

    img: Optional[ImageCube]
    
    def __init__(self, inp):
        super().__init__(inp)
        self.imagedatum = None

    def setImageCube(self, img: ImageCube):
        """Use this to set the input"""
        self.imagedatum = img

    def readData(self):
        """return the image"""
        return Datum(Datum.IMG, self.imagedatum)

    def get(self):
        """This overrides the caching method in Input; there's no point here"""
        return self.readData()

    def getName(self):
        return "Direct"

    def createWidget(self):
        return None  # returns None, which stops a button being created in the UI

    def serialise(self, internal):
        if self.imagedatum is not None:
            img = self.imagedatum.serialise()
        else:
            img = None
        return {'img': img}

    def deserialise(self, data, internal):
        if data['img'] is not None:
            self.imagedatum = ImageCube.deserialise(data['img'], self.input.mgr.doc)
        else:
            self.imagedatum = None

    def brief(self):
        if self.imagedatum is not None:
            return f"direct: {self.imagedatum.w}x{self.imagedatum.h}x{self.imagedatum.channels}"
        else:
            return "direct:none"

    def long(self):
        if self.imagedatum is not None:
            return f"direct: {str(self.imagedatum)}"
        else:
            return "direct:none"
