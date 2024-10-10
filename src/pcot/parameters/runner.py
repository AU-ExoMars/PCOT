"""
The runner module is a thin wrapper around Document which provides a way to run a document
repeatedly with different parameters set from parameter files.
"""
from pathlib import Path

from pcot.document import Document
from pcot.parameters.inputs import processParameterFileForInputs
from pcot.parameters.parameterfile import ParameterFile


class Runner:
    def __init__(self, document_path: Path):
        self.doc = Document(document_path)
        self.archive = self.doc.saveToMemoryArchive()
        self.firstTime = True

    def run(self, param_file: Path):
        """Run the document with the parameters set from the given file"""

        # we don't need to reload the document if it's the first time,
        # because the document is already loaded in the constructor.
        # We just reload to restore to the original state.
        if not self.firstTime:
            self.doc.loadFromMemoryArchive(self.archive)
        else:
            self.firstTime = False

        params = ParameterFile().load(param_file)
        processParameterFileForInputs(self.doc, params)

        # TODO run through all the nodes and apply parameters to them
