"""
This is a special object that isn't a singleton and doesn't get autoregistered.
It's used to capture an existing node's state. When we create an instance of this,
we actually create an node that has the XFormType saved in this object (I think).
"""
from xform import XFormType, XForm


class Favourite:
    def __init__(self, node:XForm):
        # capture the node state
        self.state = node.serialise()
