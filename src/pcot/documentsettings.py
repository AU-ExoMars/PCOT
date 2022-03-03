class DocumentSettings:
    """this is saved to the SETTINGS block of the document"""

    # caption types for filters
    CAP_POSITIONS = 0
    CAP_NAMES = 1
    CAP_CWL = 2
    CAP_NONE = 3

    CAP_DEFAULT = CAP_CWL

    def __init__(self):
        # integer indexing the caption type for canvases in this graph: see the box in MainWindow's ui for meanings.
        self.captionType = DocumentSettings.CAP_DEFAULT

    def serialise(self):
        return {
            'cap': self.captionType
        }

    def deserialise(self, d):
        self.captionType = d['cap']


