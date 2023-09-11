#

def serialiseFields(obj, attrs, d=None):
    """Turn some fields of an object into a dict - can also
    update an existing dict (and return it). 
    attrs is a tuple of tuples: field names and default values.
    of field names and default values."""

    ks = [x[0] for x in attrs]
    nd = {k: obj.__dict__[k] for k in ks}
    if d is not None:
        d.update(nd)
        return d
    else:
        return nd


def deserialiseFields(obj, d, attrs):
    """Turn data in a dict into object fields. Takes the dictionary
    and attrs, which (as in serialiseFields) is a tuple of tuples: field
    name and default values."""
    for k, v in attrs:
        obj.__dict__[k] = d[k] if k in d else v


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


class SignalBlocker:
    """Handy class for blocking signals on several widgets at once"""

    def __init__(self, *args):
        self.objects = args

    def __enter__(self):
        for o in self.objects:
            o.blockSignals(True)

    def __exit__(self, exctype, excval, tb):
        for o in self.objects:
            o.blockSignals(False)
