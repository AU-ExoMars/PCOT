"""
The runner module is a thin wrapper around Document which provides a way to run a document
repeatedly with different parameters set from parameter files.

Sequence of actions:
    create doc
    create runner
        runner creates archive
        runner creates paramdict
    repeatedly
        call run
            apply parameter file to paramdict (which will mod. node params) and modify inputs
            run the document
            save output
            restore the document to its original state and rebuild paramdict

OR we can do this, modifying the parameters directly

    repeatedly
        modify parameter dictionary
        call run with no parameter file
            run the document
            save output
            restore the document to its original state and rebuild paramdict

"""
from pathlib import Path
from typing import Optional

from pcot.document import Document
from pcot.inputs.inp import NUMINPUTS
from pcot.parameters.inputs import inputsDictType, modifyInput
from pcot.parameters.parameterfile import ParameterFile
from pcot.parameters.taggedaggregates import TaggedDictType, Maybe, TaggedListType

# this is the tagged dict type which holds information about output nodes and files

outputDictType = TaggedDictType(
    # which node we are getting the output from
    node=("node name", Maybe(str), None),

    # specifying None will typically mean the first output, but this is overriden
    # in some node types. For example, "sink" has no outputs, so None specifies the
    # stored value from last time. That should be the behaviour for all nodes.
    output=("node output connection (or None for the default)", Maybe(int), None),

    # the file to write to. If not provided, it should be whatever the last output was.
    # Combined with the append parameter, this allows us to write to the same file multiple times without
    # needing to specify the file and append mode each time.
    file=("output filename", Maybe(str), None),

    # clobber - if the file already exists, silently overwrite it, otherwise throw an error
    clobber=("overwrite the file if it exists", bool, False),

    # only used when we are writing a PARC
    description=("description of the data (if a PARC is being written)", Maybe(str), None),
    # only used when we are writing an image to a "standard" file (e.g. PNG, SVG, PDF).
    drawAnnotations=("draw ROIs/annotations on the image (not for PARC)", bool, True),

    # if we are writing a PARC this is the name of the item we are going to store in the archive. If it is already
    # there, we will add -N to the name until we find a free slot. If it is None, we will use name "main"
    name=("name of the datum in the archive", Maybe(str), None),

    # only used when we are writing a text file or PARC. In the latter case, the datum will be appended to the archive
    # if there is no existing datum of that name (see 'name' above). The default value None means whatever the previous
    # output was set to, unless there wasn't one, in which case it will be False.
    append=("append to a PARC or text file if it exists", Maybe(bool), None),

    # if we're outputting to a text file, this string will be prefixed to the output. It's a good place to put
    # a header, for example. Note that this is not used for PARC files, and does not apply to images.
    # The string will be immediately followed by the output - add any desired whitespace or separators.
    prefix=("prefix for the output", Maybe(str), None),

    # options=("options for the output", dict, {}),    # miscellaneous options for the datum's writeToFile method
)

# we have a list of outputs
outputListType = TaggedListType("output list", outputDictType, 0)


class Runner:
    def __init__(self, document_path: Path):
        self.doc = Document(document_path)
        self.archive = self.doc.saveToMemoryArchive()
        self._build_param_dict()

    def _build_param_dict(self):
        # we create a dict for each of the TaggedDicts we are working
        # with in the document. These will be modified by parameter files
        # (and possibly directly).

        # first, the inputs - this dict will be used to modify the inputs
        # in the document. It's a fresh dict each time.
        # We also build an output dict, saying where the output should go.
        self.paramdict = {'inputs': inputsDictType.create(),
                          'outputs': outputListType.create()}

        # now one for each node. Here, we're referencing dicts that exist inside
        # the nodes themselves.
        # You might get problems here if you have multiple
        # nodes with the same display name - later nodes will overwrite earlier ones.
        for node in self.doc.graph.nodes:
            # we even do this if the node has no parameters so we can check for that.
            self.paramdict[node.displayName] = node.params

    def run(self, param_file: Optional[Path], param_file_text: Optional[str] = None):
        """Run the document with the parameters set from the given file. The param_file_text
        is provided for testing - it allows a parameter file to be passed in as a string."""

        try:
            if param_file:
                params = ParameterFile().load(param_file)
                # Apply the parameter file to the parameters in the paramdict.
                params.apply(self.paramdict)
                # The nodes will be modified, but the modifications to the inputs
                # need to be processed separately.
            elif param_file_text:
                params = ParameterFile().parse(param_file_text)
                params.apply(self.paramdict)

            # we MAY have run a parameter file, but the input parameters may have been modified
            # directly. We need to apply these to the inputs. No need to worry about the nodes
            # as they are already modified. Ditto the output parameters, which are handled in
            # writeOutputs.
            for i in range(NUMINPUTS):
                # note that we are using the string representation of the input numbers as keys
                ii = self.paramdict['inputs'][str(i)]
                inp = self.doc.inputMgr.getInput(i)
                modifyInput(ii, inp)

            # run the document
            self.doc.run()

            self.writeOutputs()
        finally:
            # restore the document to its original state and rebuild the paramdict ready
            # for the next run. This is in a finally block in case any of the above code
            # throws an exception - we definitely want to restore!
            self.doc.loadFromMemoryArchive(self.archive)
            self._build_param_dict()

    def writeOutputs(self):
        """This checks the parameter dict for an output node and file. We could alternatively
        store output file names in the sink node, but this is a quick and dirty (and perhaps better) way to
        do it"""

        # these two variables are used if the file or append mode is not specified for an output;
        # they will be set to the last filename and append mode used.
        prev_filename = None
        prev_append = False
        for v in self.paramdict['outputs']:
            if v.file is None:
                v.file = prev_filename
            if v.append is None:
                v.append = prev_append
            prev_filename = v.file
            prev_append = v.append

            if v.node is not None and v.file is not None:
                # get the node
                node = self.doc.graph.getByDisplayName(v.node, single=True)
                if v.output is None:
                    # no output connector is specified, so get the default output value, which is not
                    # necessarily the value of any output connection (c.f sink, which has no actual outputs)
                    output = node.type.getBatchOutputValue(node)
                else:
                    # otherwise get the output
                    output = node.getOutputDatum(int(v.output))
                # write it to the file if we can
                if output is None:
                    raise ValueError(f"No output from node {v.node}")

                # we pass the ENTIRE output dict to the writeToFile method. It's a little ugly with quite a
                # bit of unnecessary information for some cases, but at least the method signature is simple
                # and the data well-organised (as it's a TaggedDict).
                output.writeFile(v)
