class DatumException(Exception):
    """Exception class for Datum exceptions. Not (at the moment) a subclass XFormException,
    so gets handled slightly differently when run in a perform()."""
    def __init__(self, message):
        super().__init__(message)


class InvalidTypeForDatum(DatumException):
    """Exception for when Datum() is called with a value that is not valid for the datum type given"""
    def __init__(self, message):
        super().__init__(message)


class CannotSerialiseDatumType(DatumException):
    """thrown when we try to serialise/deserialise a datum type which can't be."""
    def __init__(self, typename):
        super().__init__(f"Datum type {typename} is not yet serialisable")


class UnknownDatumTypeException(DatumException):
    """thrown when we try to process an unknown datum type by name."""
    def __init__(self, typename):
        super().__init__(f"Datum type {typename} is unknown")


class BadDatumCtorCallException(DatumException):
    """Thrown when we try to init a datum with the wrong arguments."""
    def __init__(self):
        super().__init__("bad call to datum ctor: should be Datum(type,val)")


class DatumWithNoSourcesException(DatumException):
    """Datum constructor should be supplied with explicit source set if not an image or None"""
    def __init__(self):
        super().__init__("Datum objects which are not images must have an explicit source set")


class NoDatumCopy(DatumException):
    def __init__(self, typename):
        super().__init__(f"Datum type {typename} has no copy operation")
