from typing import Union, Optional

# Source Types
from pcot import dq

STypeChannel = 1        # data comes from a single channel (the source field gives the brief name)
STypeMaxAll = 2         # data is max of all channels (union if bits)
STypeSumAll = 3         # data is sum of all channels (union if bits)

DTypeNone = 0           # inactive
DTypeUnc = -1           # for 'data' field in CanvasDQSpec, means uncertainty
DTypeUncThresh = -2     # for 'data', means a boolean: uncertainty>threshold


class CanvasDQSpec:
    stype: int      # source type, see above
    source: str     # see SpecTypeChannel; invalid for others
    data: int       # the data we're examining. If -ve, means a DType.. above. If 0, means none. Positive is a DQ bit.
    col: str        # colour name for display

    @staticmethod
    def getDataItems():
        """Return a list of (name,int) tuples for the data fields"""
        x = [(name, val) for name, val in dq.DQs.items()]
        x.append(('NONE', 0))
        x.append(('UNC', -1))
        x.append(('UNCTHR', -2))
        return x

    def serialise(self):
        return {
            'stype': self.stype,
            'source': self.source,
            'data': self.data,
            'col': self.col
        }

    def deserialise(self, d):
        self.stype = d.get('stype', STypeMaxAll)
        self.source = d.get('source', None)
        self.data = d.get('data', DTypeNone)
        self.col = d.get('col', 'magenta')

    def __init__(self):
        self.deserialise({})
