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


class SingletonException(Exception):
    """"Don't call a singleton constructor directly; use instance()"""

    def __init__(self):
        super().__init__("singletons must be accessed through calls to instance()")


# noinspection PyPep8Naming
class singleton:
    """Decorator to create a singleton class. Never call the constructor directly, call instance()"""

    def __init__(self, c):
        self._singleton_class = c

    def instance(self):
        """returns the singleton instance. First call creates the instance."""
        try:
            return self._inst
        except AttributeError:
            self._inst = self._singleton_class()
            return self._inst

    def __call__(self):
        raise SingletonException()
