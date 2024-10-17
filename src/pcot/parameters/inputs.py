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
    # either filenames or wildcard can be set, but not both. If filenames is non-zero length we use it.
    filenames=("list of filenames (mutually exclusive with 'wildcard')",
               TaggedListType("filename", str, [], '')),
    wildcard=("wildcard for filenames (mutually exclusive with 'filenames')", Maybe(str), None),
    filter_pattern=("pattern for filter identification", str, r".*(?P<lens>L|R)WAC(?P<n>[0-9][0-9]).*"),
    filter_set=("name of filter set to use", str, "PANCAM"),
    bit_depth=("number of bits used in the image (default is all bits)", Maybe(int), None),
    preset=("preset name for some params (can be overridden by other params)", Maybe(str), None),
    raw=("parameters for loading raw data", TaggedDictType(
        format=("integer format (u16 u8 or f32)", str, "u16"),  # default is uint16
        width=("image width", int, 1024),
        height=("image height", int, 1024),
        bigendian=("whether the data is big-endian", bool, False),
        offset=("size of the header in bytes (this is skipped)", int, 0),
        rot=("counter-clockwise rotation of the image in degrees (must be multiple of 90)", int, 0),
        horzflip=("whether the image is flipped horizontally (after rotation)", bool, False),
        vertflip=("whether the image is flipped vertically (after rotation)", bool, False))
         )
)

# PDS4 - this may change a lot later on.

PDS4DictType = TaggedDictType(
    directory=("directory to load from", Maybe(str), None),  # if not present, we are inactive
    filenames=("list of filenames (mutually exclusive with 'wildcard')",
               TaggedListType("filename", str, [], '')),
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
    parc=("PCOT datum archive input method", PARCDictType, None),

    direct=("Direct input method", rgbDictType, None))   # not actually valid, but we need a placeholder

# and there are N inputs

kwargs = {f"{i}": (f"input {i}", inputMethodDictType, None) for i in range(NUMINPUTS)}
inputsDictType = TaggedDictType(**kwargs)


def processParameterFileForInputsTest(doc: Document, p: ParameterFile):
    """Creates an input dict with the inputsDictType specification, and modifies it
    using a parameter file. Then uses any inputs actually set in the dict to modify
    the live inputs in the document. This is for testing purposes only,
    the live system uses runner.run() to call modifyInputs.
    """

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


def modifyInput(inputDict, inp: Input):
    """Modifies an input object based on a dict."""

    # we have to modify all the methods in the input object,
    # because we don't know which one is active. In fact, it's
    # likely that none of them are active (i.e. null is). We want
    # the modification to actually set the active method. However,
    # once we have modified one method we skip the others.

    for method in inp.methods:
        if method.modifyWithParameterDict(inputDict):
            # the method was modified, so we need to select it and force reload
            inp.selectMethod(method)
            method.invalidate()
            method.get()
            if inp.exception is not None:
                # if there was an exception, we need to stop
                raise Exception(f"Error in input {inp.idx}: {inp.exception}")
            # skip the rest of the methods
            break

