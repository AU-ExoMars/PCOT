"""
This is a special object that isn't a singleton and doesn't get autoregistered.
It's used to capture an existing node's state. When we create an instance of this,
we actually create an node that has the XFormType saved in this object (I think).
"""
from pcot.xform import XForm, XFormType


class Favourite:
    def __init__(self, name:str=None, node:XForm=None, json=None):
        """Create a Favourite object, either from a node or from serialised data (when loading)
        Usage either
            Favourite(node=node)
        or
            Favourite(json=jsondata)
        """
        if json:
            self.name = json['name']
            self.state = json['state']
            self.typename = json['type']
        elif node:
            if name is None:
                raise ValueError("Must provide name when creating Favourite from node")
            self.name = name
            self.state = node.serialise()
            self.typename = node.type.name
        else:
            raise ValueError("Node or json must be provided to create a Favourite")

    def createNode(self, graph):
        node = graph.create(self.typename)
        node.deserialise(self.state)
        return node

    def serialise(self):
        return {'name': self.name, 'type': self.typename, 'state': self.state}
