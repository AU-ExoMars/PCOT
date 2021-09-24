"""This package deals with inputs into PCOT and input methods.
The three main classes here are:
    InputManager: manages a number of Inputs for an XFormGraph/Document
    Input: handles input. Has a number of InputMethods, only one of which is active
    InputMethod: REALLY handles input - this is an interface which is implemented
        for each way of reading each kind of input.


"""

from .inp import Input
