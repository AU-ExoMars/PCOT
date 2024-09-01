"""
Test modifications to inputs by parameter files
"""
import pcot
from pcot.document import Document
from pcot.parameters.inputs import processParameterFile
from pcot.parameters.parameterfile import ParameterFile


def test_no_items():
    pcot.setup()
    d = Document()
    f = ParameterFile().parse("")
    processParameterFile(d, f)
