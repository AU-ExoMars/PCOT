from typing import Any, List, Callable, Optional


class datumfunc:
    """This is a decorator for functions which are to be registered as expression functions.
    The function must take a list of mandatory arguments and a list of optional arguments, and return a Datum.
    The function is registered under the name given in the first argument.
    """

    registry = {}

    name: str
    description: str
    mandatoryParams: List['Parameter']
    optParams: List['Parameter']
    varargs: bool

    def __init__(self,
                 desc: str,
                 mandatoryParams: List['Parameter'],
                 optParams: Optional[List['Parameter']] = None,
                 varargs: bool=False):
        self.description = desc
        self.mandatoryParams = mandatoryParams
        self.optParams = optParams if optParams is not None else []
        self.varargs = varargs
        # TODO this code ends up being duplicated in the Function ctor.
        if self.varargs and len(self.mandatoryParams) == 0:
            raise Exception("cannot have a function with varargs but no mandatory arguments")
        elif self.varargs and len(self.optParams) > 0:
            raise Exception("cannot have a function with varargs and optional arguments")

    def __call__(self, func: Callable[[List[Any], List[Any]], Any]):
        """This actually decorates the function, while the constructor just sets up this object
        which is used to store data about the function and register it.

        This method - the decorator proper - does two things.

        1. It stores the function pointer in the registry object
        2. It returns a wrapper to the passed in function, which is the actual function that will be called
        in a "normal" Python call.
        """
        # store our data in the registry along with the function name and the function pointer
        self.name = func.__name__
        self.registry[self.name] = self
        self.func = func

        def wrapper(*args, **kwargs):
            # we need to extract the args into a list of Datum objects. If there are too many args, we move
            # the excess into the optional list. If the optional list isn't long enough, we pad it with None.
            ct = len(self.mandatoryParams)
            from pcot.datum import convert2datum
            mandatory = [convert2datum(x) for x in args[:ct]]
            # if there aren't enough mandatory arguments, we raise an error
            if len(mandatory) < ct:
                raise ValueError(f"Function {self.name} requires at least {ct} arguments")
            # now we handle varargs, which just get appended to the mandatory list
            if self.varargs:
                mandatory += [convert2datum(x) for x in args[ct:]]
                optional = []
            else:
                # if there are no varargs, we can process optional args
                optional = [convert2datum(x) for x in args[ct:]]
                optional += [None] * (len(self.optParams) - len(optional))
            # we can now call the original function with the Datum objects
            return self.func(mandatory, optional)
        return wrapper

    @classmethod
    def get(cls, name):
        """get a function from the registry by name"""
        return cls.registry.get(name)


# @datumfunc(2, 2)
def main(mandatory: List[Any], optional: List[Any]):
    """This is a test function which takes a list of mandatory arguments and a list of optional arguments."""
    print(mandatory)
    print(optional)
    return 10


#print(datumfunc.get("main").fp)
#f = main(1,2)
#print(f)
