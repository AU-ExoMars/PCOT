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
from pcot.parameters.inputs import processParameterFileForInputsTest, inputsDictType, modifyInput
from pcot.parameters.parameterfile import ParameterFile


class Runner:
    def __init__(self, document_path: Path):
        self.doc = Document(document_path)
        self.archive = self.doc.saveToMemoryArchive()
        self._build_paramdict()

    def _build_paramdict(self):
        # we create a dict for each of the TaggedDicts we are working
        # with in the document. These will be modified by parameter files
        # (and possibly directly).

        # first, the inputs - this dict will be used to modify the inputs
        # in the document. It's a fresh dict each time.
        self.paramdict = {'inputs': inputsDictType.create()}

        # now one for each node. Here, we're referencing dicts that exist inside
        # the nodes themselves.
        # You might get problems here if you have multiple
        # nodes with the same display name - later nodes will overwrite earlier ones.
        for node in self.doc.graph.nodes:
            # we even do this if the node has no parameters so we can check for that.
            self.paramdict[node.displayName] = node.params

    def run(self, param_file: Optional[Path]):
        """Run the document with the parameters set from the given file"""
        if param_file:
            params = ParameterFile().load(param_file)
            # Apply the parameter file to the parameters in the paramdict.
            params.apply(self.paramdict)
            # The nodes will be modified, but the modifications to the inputs
            # need to be processed separately.

        # we MAY have run a parameter file, but the input parameters may have been modified
        # directly. We need to apply these to the inputs. No need to worry about the nodes
        # as they are already modified.
        for i in range(NUMINPUTS):
            # note that we are using the string representation of the input numbers as keys
            ii = self.paramdict['inputs'][str(i)]
            inp = self.doc.inputMgr.getInput(i)
            modifyInput(ii, inp)

        # run the document
        self.doc.run()

        # TODO save the output

        # restore the document to its original state and rebuild the paramdict ready
        # for the next run
        self.doc.loadFromMemoryArchive(self.archive)
        self._build_paramdict()

