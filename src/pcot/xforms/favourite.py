"""
This is a special object that isn't a singleton and doesn't get autoregistered.
It's used to capture an existing node's state. When we create an instance of this,
we actually create an node that has the XFormType saved in this object (I think).
"""
from pcot.xform import XForm


class Favourite:
    def __init__(self, node:XForm):
        # capture the node state
        self.state = node.serialise()
        self.typename = node.type.name

    def createNode(self, graph):
        node = graph.create(self.state['type'])
        node.deserialise(self.state)
        return node