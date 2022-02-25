## the Null input, which does nothing and outputs None

from .inputmethod import InputMethod
from pcot.ui.inputs import PlaceholderMethodWidget
from ..datum import Datum


class NullInputMethod(InputMethod):
    def __init__(self, inp):
        super().__init__(inp)

    def readData(self):
        """Here we output a null datum"""
        return Datum.null

    def getName(self):
        return "Null"

    def createWidget(self):
        return PlaceholderMethodWidget(self)

    def serialise(self, internal):
        return None

    def deserialise(self, data, internal):
        pass

    def brief(self):
        """really this should never be seen"""
        return "null"

    def long(self):
        """really this should never be seen"""
        return "null"
