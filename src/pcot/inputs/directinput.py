from typing import Optional

from .inputmethod import InputMethod
from ..datum import Datum
from ..imagecube import ImageCube
from ..parameters.taggedaggregates import TaggedDict


class DirectInputMethod(InputMethod):
    """the direct method, which lets script authors get a Datum into the graph.
    Not accessible via the GUI"""

    datum: Datum
    
    def __init__(self, inp):
        super().__init__(inp)
        self.datum = Datum.null

    def setDatum(self, d: Datum):
        """Use this to set the input"""
        self.datum = d

    def setImageCube(self, img: ImageCube) -> InputMethod:
        """Use this to set the input to an imagecube"""
        self.setDatum(Datum(Datum.IMG, img))
        return self

    def readData(self):
        """returns the datum"""
        return self.datum

    def get(self):
        """This overrides the caching method in Input; there's no point here"""
        return self.readData()

    def getName(self):
        return "Direct"

    def createWidget(self):
        return None  # returns None, which stops a button being created in the UI

    def serialise(self, internal):
        return {'d': self.datum.serialise()}

    def deserialise(self, data, internal):
        if 'd' in data and data['d'] is not None:
            self.datum = Datum.deserialise(data['d'])
        else:
            self.datum = Datum.null  # could happen in legacy files

    def modifyWithParameterDict(self, d: TaggedDict) -> bool:
        if d.direct.filename is not None:
            raise Exception("Direct input method parameters not supported")
        return False
