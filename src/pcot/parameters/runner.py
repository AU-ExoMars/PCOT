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
import datetime
import logging
import os
from pathlib import Path
from typing import Optional, Any, Dict

from jinja2 import Environment

from pcot.document import Document
from pcot.inputs.inp import NUMINPUTS
from pcot.parameters.inputs import inputsDictType, modifyInput
from pcot.parameters.parameterfile import ParameterFile
from pcot.parameters.taggedaggregates import TaggedDictType, Maybe, TaggedListType, TaggedAggregate

logger = logging.getLogger(__name__)

# this is the tagged dict type which holds information about output nodes and files

VALID_IMAGE_OUTPUT_FORMATS = ['pdf', 'svg', 'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'parc']
VALID_TEXT_OUTPUT_FORMATS = ['txt', 'csv']

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
    file=("output filename - if not provided, use previous output's value (see 'append')", Maybe(str), None),

    clobber=("overwrite the file if it exists (else raise an exception)", bool, False),
    format=("output format for image in lowercase (will determine from extension if not given)", Maybe(str), None,
            VALID_TEXT_OUTPUT_FORMATS + VALID_IMAGE_OUTPUT_FORMATS),
    annotations=(
    "draw ROIs/annotations on the image (must be false for PARC). If not provided, use previous output's value (or false if first output)",
    Maybe(bool), None),

    name=("name of the datum (if a PARC is being written) - 'main' if not given", Maybe(str), None),
    description=("description of the data (if a PARC is being written)", Maybe(str), None),
    width=(
    "width of output image when exporting to raster formats (in pixels) if annotations is true. If annotations is false or width is negative, no resizing is done.",
    int, 1000),

    # only used when we are writing a text file or PARC. In the latter case, the datum will be appended to the archive
    # if there is no existing datum of that name (see 'name' above). The default value None means whatever the previous
    # output was set to, unless there wasn't one, in which case it will be False.
    append=(
    "append to a PARC or text file if it exists. If not provided, use previous output's value (or false if first output)",
    Maybe(bool), None),

    # if we're outputting to a text file, this string will be prefixed to the output. It's a good place to put
    # a header, for example. Note that this is not used for PARC files, and does not apply to images.
    # The string will be immediately followed by the output - add any desired whitespace or separators.
    prefix=("prefix for the output (text outputs only)", Maybe(str), None),
)

# we have a list of outputs
outputListType = TaggedListType("output list", outputDictType, 0)


class Runner:
    def __init__(self, document_path: Path, jinja_env: Optional[Environment] = None):
        """Create a runner. The document is loaded from the given path. The jinja_env is an optional
        Jinja2 environment; if not provided one is created. You can use this to add custom filters
        and functions to the templating engine. Some are added by default (see below).
        """
        self.doc = Document(document_path)
        self.document_path = document_path
        self.count = 0
        self.archive = self.doc.saveToMemoryArchive()
        self._build_param_dict()

        if jinja_env is None:
            # create one if it wasn't provided
            jinja_env = Environment()

        # add stuff to the Jinja2 environment - this will, of course, override any custom things with the same
        # name that you may already have added.

        # IF YOU CHANGE THIS, REMEMBER TO CHANGE mkdocs/docs/userguide/batch/params.md

        jinja_env.filters['basename'] = os.path.basename  # return the last part of a file path: foo/bar.png -> bar.png
        jinja_env.filters['dirname'] = os.path.dirname  # return the directory part of a file path: foo/bar.png -> foo
        jinja_env.filters['stripext'] = lambda xx: os.path.splitext(xx)[0]  # remove extension: foo.bar -> foo
        jinja_env.filters['extension'] = lambda xx: os.path.splitext(xx)[1]  # get extension: foo.bar -> .bar

        self.jinja_env = jinja_env

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

        # create the 'originals' which will be used to reset the parameters with
        # the "reset" commands
        for p in self.paramdict.values():
            if isinstance(p, TaggedAggregate):
                p.generate_original()

    def run(self, param_file: Optional[Path], param_file_text: Optional[str] = None,
            data_for_template: Optional[Dict[str, Any]] = None):
        """Run the document with the parameters set from the given file. The param_file_text
        is provided for testing - it allows a parameter file to be passed in as a string.
        The data_for_template is a dictionary which will be used to fill in template strings
        (in Jinja2 format) in the parameter file.
 
       Some template items are preset:

       IF YOU CHANGE THIS, REMEMBER TO CHANGE mkdocs/docs/userguide/batch/params.md

            - {{docpath}} - the path to the document (with backslashes replaced by forward slashes)
            - {{docfile}} - the name of the document file (i.e. the final part of the path)
            - {{datetime}} - the current date and time in ISO 8601 format
            - {{date}} - the current date in ISO 8601 format
            - {{count}} - the number of times the document has been run (useful in loops)
            - {{parampath}} - the path to the parameter file (if one is used, it is "NoFile" otherwise)
            - {{paramfile}} - the name of the parameter file (if one is used, it is "NoFile" otherwise)


        See also some useful filters we add to the Jinja2 environment in the constructor.
        """

        # make sure a dict exists for the templater
        data_for_template = data_for_template or {}
        # and merge in the preset values
        data_for_template.update({
            "docpath": str(self.document_path).replace("\\", "/"),
            "docfile": str(self.document_path.name),
            "datetime": datetime.datetime.now().isoformat(),
            "date": datetime.datetime.now().date().isoformat(),
            "count": self.count})

        self.count += 1

        try:
            def run():
                logger.info("Running the document")

                # now tell all the nodes in the graph that use CTAS (complex TaggedAggregate serialisation)
                # to reconstruct their data from the modified parameters.
                self.doc.graph.nodeDataFromParams()

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
                # see if there were any errors in the run
                error_nodes = self.doc.graph.getAnyErrors()
                if len(error_nodes) > 0:
                    error_msg = ""
                    for node in error_nodes:
                        logger.error(f"Error in node {node.displayName} - {node.error}")
                        error_msg += f" {node.displayName} - {node.error}\n"
                    raise ValueError(f"Errors in run ({len(error_nodes)} nodes failed):\n{error_msg}")

                # write the outputs
                self.writeOutputs()

            if param_file:
                # this if we are running from an actual parameter file on disk
                data_for_template.update({
                    "parampath": str(param_file).replace("\\", "/"),
                    "paramfile": str(param_file.name)
                })
                params = ParameterFile(self.jinja_env, run).load(param_file, data_for_template)
                # Apply the parameter file to the parameters in the paramdict.
                params.apply(self.paramdict)
                # The nodes will be modified, but the modifications to the inputs
                # need to be processed separately inside the run function
            elif param_file_text:
                # this if we are running from a block of text
                data_for_template.update({
                    "parampath": "NoFile",
                    "paramfile": "NoFile"
                })
                params = ParameterFile(self.jinja_env, run).parse(param_file_text, data_for_template)
                params.apply(self.paramdict)
        finally:
            # restore the document to its original state and rebuild the paramdict ready
            # for the next run. This is in a finally block in case any of the above code
            # throws an exception - we definitely want to restore!
            logger.debug("Restoring document to original state")
            self.doc.loadFromMemoryArchive(self.archive)
            logger.debug("rebuilding param dict")
            self._build_param_dict()
            logger.debug("rebuild done")

    def writeOutputs(self):
        """This checks the parameter dict for an output node and file. We could alternatively
        store output file names in the sink node, but this is a quick and dirty (and perhaps better) way to
        do it"""

        # these variables are used if the file or append mode is not specified for an output;
        # they will be set to the last filename and append mode used. Same with annotations (added later)
        prev_filename = None
        prev_append = False
        prev_annot = True  # annotations are exported by default
        if len(self.paramdict['outputs']) == 0:
            logger.warn("No outputs provided for this parameter file")
        for v in self.paramdict['outputs']:
            if v.file is None:
                v.file = prev_filename
            if v.append is None:
                v.append = prev_append
            if v.annotations is None:
                v.annotations = prev_annot

            prev_filename = v.file
            prev_append = v.append
            prev_annot = v.annotations

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

                # we pass the ENTIRE output dict to the file writing method. It's a little ugly with quite a
                # bit of unnecessary information for some cases, but at least the method signature is simple
                # and the data well-organised (as it's a TaggedDict).
                logger.info(f"writing output to {v.file}")
                output.writeBatchOutputFile(v)
