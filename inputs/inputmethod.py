## defines a way of inputting data (image data, usually). Each input has several
# of this which are all always present, but only one is active (determined by
# its index in the Input).

class InputMethod:
    def __init__(self, inp):
        self.input = inp
        self.name = ''

    ## asks the input if I'm active
    def isActive(self):
        return self.input.isActive(self)

    ## to override - actually runs the input and returns data
    def get(self):
        return None

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
