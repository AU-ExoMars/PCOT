## the Null input, which does nothing and outputs None

from inputs.inputmethod import InputMethod
from ui.inputs import PlaceholderMethodWidget


class NullInputMethod(InputMethod):
    def __init__(self, inp):
        super().__init__(inp)

    def get(self):
        return None

    def getName(self):
        return "Null"

    def createWidget(self):
        return PlaceholderMethodWidget(self)

    def serialise(self):
        pass

    def deserialise(self, data):
        pass
