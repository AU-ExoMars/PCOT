from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.xform import XFormType, xformtype


@xformtype
class XFormDummy(XFormType):
    """
    A dummy node type used when the node type specified in a loaded file cannot be found - perhaps it is from
    an older PCOT version and is now deprecated, or it's part of a plugin?"""
    def __init__(self):
        super().__init__("dummy", "hidden", "0.0.0")
        self.params = TaggedDictType()  # no parameters

    def createTab(self, n, w):
        pass

    def init(self, n):
        pass

    def perform(self, n):
        pass

    def deserialise(self, n, d):
        # replace the node display name, so we know it's a dummy node but we also know what it was
        n.displayName = "dummy ({})".format(d['displayName'])
