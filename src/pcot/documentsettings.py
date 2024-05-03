class DocumentSettings:
    """this is saved to the SETTINGS block of the document"""

    captionType: int
    alpha: int    # transparency of annotations on the canvas (NOT in exported images). 0-100 because slider.

    # caption types for filters
    CAP_POSITIONS = 0
    CAP_NAMES = 1
    CAP_CWL = 2
    CAP_NONE = 3

    CAP_DEFAULT = CAP_CWL

    def __init__(self):
        # integer indexing the caption type for canvases in this graph: see the box in MainWindow's ui for meanings.
        self.captionType = DocumentSettings.CAP_DEFAULT
        self.alpha = 100

    def serialise(self):
        return {
            'cap': self.captionType,
            'alpha': self.alpha
        }

    def deserialise(self, d):
        self.captionType = d.get('cap', DocumentSettings.CAP_DEFAULT)
        self.alpha = d.get('alpha', 100)


