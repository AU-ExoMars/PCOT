## the Null input, which does nothing and outputs None

from pcot.inputs.inputmethod import InputMethod
from pcot.ui.inputs import PlaceholderMethodWidget


class NullInputMethod(InputMethod):
    def __init__(self, inp):
        super().__init__(inp)

    def readData(self):
        return None

    def getName(self):
        return "Null"

    def createWidget(self):
        return PlaceholderMethodWidget(self)

    def serialise(self, internal):
        return None

    def deserialise(self, data, internal):
        pass
