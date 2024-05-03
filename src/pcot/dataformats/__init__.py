"""
Code for dealing with the low-level loading of data formats. The code in here should be called
by the InputMethods. The code in "load" should be able to load data from a file and return a
Datum object. Code in other files is for more complex things (e.g. PDS4, ENVI, etc.)
"""
