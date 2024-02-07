
from .inputmethod import InputMethod
from pcot.ui.inputs import NullMethodWidget
from ..datum import Datum


class NullInputMethod(InputMethod):
    """the Null input, which does nothing and outputs None"""

    def __init__(self, inp):
        super().__init__(inp)

    def readData(self):
        """Here we output a null datum"""
        return Datum.null

    def getName(self):
        return "Null"

    def createWidget(self):
        return NullMethodWidget(self)

    def serialise(self, internal):
        return None

    def deserialise(self, data, internal):
        pass

