## defines a way of inputting data (image data, usually). Each input has several
# of this which are all always present, but only one is active (determined by
# its index in the Input).
from typing import Optional, Any


class InputMethod:
    def __init__(self, inp):
        self.input = inp
        self.name = ''
        self.data = None

    ## asks the input if I'm active
    def isActive(self):
        return self.input.isActive(self)

    ## to override - actually runs the input and returns data.
    def readData(self) -> Optional[Any]:
        return None

    ## invalidates
    def invalidate(self):
        self.data = None

    ##  returns the cached data
    def get(self):
        return self.data

    ## reads the data if the cache has been invalidated
    def read(self):
        if self.data is None:
            if self.data is None:
                self.data = self.readData()
                if self.data is not None:
                    print("CACHE WAS INVALID, DATA READ")

    ## to override - returns the name for display purposes
    def getName(self):
        return ''

    ## to override - creates the editing widget in the input window
    def createWidget(self):
        pass

    ## to override - converts this object's state into a bunch of plain data
    # which can be converted to JSON
    def serialise(self):
        return None

    ## to override - sets this method's data from JSON-read data
    def deserialise(self, data):
        raise Exception("InputMethod does not have a deserialise method")

