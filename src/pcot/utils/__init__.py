#

def serialiseFields(obj, attrnames, d=None):
    """Turn some fields of an object into a dict - can also
    update an existing dict (and return it)"""

    nd = {k: obj.__dict__[k] for k in attrnames}
    if d is not None:
        d.update(nd)
        return d
    else:
        return nd


def deserialiseFields(obj, d, attrnames):
    """Turn data in a dict into object fields"""
    for x in attrnames:
        if x in d:
            obj.__dict__[x] = d[x]