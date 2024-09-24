"""
Handling how parameter files can modify inputs.
"""
from pcot.document import Document
from pcot.inputs.inp import NUMINPUTS, Input
from pcot.parameters.parameterfile import ParameterFile
# first we define the tagged dict type for each input type

from pcot.parameters.taggedaggregates import TaggedDictType, TaggedListType, Maybe

# RGB inputs don't have much - just a filename.
rgbDictType = TaggedDictType(
    filename=("filename", Maybe(str), None)
)

# ENVI files also just have a filename WITHOUT an extension (remember that ENVI
# files are actually two files, one with the .hdr extension and one with .dat).
enviDictType = TaggedDictType(
    filename=("filename (without extension)", Maybe(str), None)
)

# Multifile input is rather more complex. We have two ways of specifying the files:
# a list of filenames, or a single filename with a wildcard. We also need to have a
# pattern to get the filter names/positions, and several options - including how to
# process binary data.
multifileDictType = TaggedDictType(
    directory=("directory to load from", Maybe(str), None),  # if not present, we are inactive
    filenames=("list of filenames (mutually exclusive with 'wildcard')",
               Maybe(TaggedListType("filename", str, [])), None),
    wildcard=("wildcard for filenames (mutually exclusive with 'filenames')", Maybe(str), None),
    filter_pattern=("pattern for filter identification", str, r".*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*"),
    filter_set=("name of filter set to use", str, "PANCAM"),
    bit_depth=("number of bits used in the image (default is all bits)", Maybe(int), None),
    raw_preset=("preset for loading raw data (overriden by raw_params)", Maybe(str), None),
    raw_params=("parameters for loading raw data", TaggedDictType(
        format=("integer format (e.g. uint16, which is the default", str, "uint16"),  # default is uint16
        width=("image width", int, 1024),
        height=("image height", int, 1024),
        bigendian=("whether the data is big-endian", bool, False),
        offset=("size of the header in bytes (this is skipped)", int, 0),
        rot=("counter-clockwise rotation of the image in degrees (must be multiple of 90)", int, 0),
        horzflip=("whether the image is flipped horizontally (after rotation)", bool, False),
        vertflip=("whether the image is flipped vertically (after rotation)", bool, False)),
                None)
)

# PDS4 - this may change a lot later on.

PDS4DictType = TaggedDictType(
    directory=("directory to load from", Maybe(str), None),  # if not present, we are inactive
    filenames=("list of filenames (mutually exclusive with 'wildcard')",
               Maybe(TaggedListType("filename", str, [])), None),
    wildcard=("wildcard for filenames (mutually exclusive with 'filenames')", Maybe(str), None)
)

# PARC - PCOT datum archive file

PARCDictType = TaggedDictType(
    filename=("filename", Maybe(str), None),
    itemname=("name of the item in the archive", Maybe(str), 'main')
)

# now we define the tagged dict type for the entire input method. The active input method is
# the one which has certain key fields filled in.

inputMethodDictType = TaggedDictType(
    rgb=("RGB input method", rgbDictType, None),
    envi=("ENVI input method", enviDictType, None),
    multifile=("Multifile input method", multifileDictType, None),
    pds4=("PDS4 input method", PDS4DictType, None),
    parc=("PCOT datum drchive input method", PARCDictType, None),

    direct=("Direct input method", rgbDictType, None))   # not actually valid, but we need a placeholder

# and there are N inputs

kwargs = {f"{i}": (f"input {i}", inputMethodDictType, None) for i in range(NUMINPUTS)}
inputsDictType = TaggedDictType(**kwargs)


def processParameterFileForInputs(doc: Document, p: ParameterFile):
    """Creates an input dict with the inputsDictType specification, and modifies it
    using a parameter file. Then uses any inputs actually set in the dict to modify
    the live inputs in the document."""

    # create the dictionary
    inputs = inputsDictType.create()
    # apply the parameter file to this dictionary, modifying it using the
    # name "inputs" - so input 0 will be a subtree from "input.0" downwards.
    p.apply({"inputs": inputs})

    # having modified the dictionary, we now need to apply it to the actual inputs
    # in the document.
    for i in range(NUMINPUTS):
        # note that we are using the string representation of the input numbers as keys
        ii = inputs[str(i)]
        inp = doc.inputMgr.getInput(i)
        modifyInput(ii, inp)

    # TODO apply the inputs to the document's nodes
    # TODO add a call to this method in the document's load method


def modifyInput(inputDict, inp: Input):
    """Modifies an input object based on a dict."""

    # we have to modify all the methods in the input object,
    # because we don't know which one is active. In fact, it's
    # likely that none of them are active (i.e. null is). We want
    # the modification to actually set the active method.
    for method in inp.methods:
        if method.modifyWithParameterDict(inputDict):
            # the method was modified, so we need to select it and force reload
            inp.selectMethod(method)
            method.invalidate()
            method.get()
            # skip the rest of the methods
            break
