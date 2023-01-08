from typing import Union, Optional

# Source Types
from pcot import dq

# values of stype
STypeChannel = 1        # data comes from a single channel (the channel field gives the index in the canvas)
STypeMaxAll = 2         # data is max of all channels (or union if data>0 - it's a DQ bit)
STypeSumAll = 3         # data is sum of all channels (or union if data>0 - it's a DQ bit)

# values of data field, not including positive values which are DQ bit masks.
DTypeNone = 0           # inactive
DTypeUnc = -1           # for 'data' field in CanvasDQSpec, means uncertainty
DTypeUncThresh = -2     # for 'data', means a boolean: uncertainty>threshold


class CanvasDQSpec:
    stype: int      # source type, see above
    channel: int     # see STypeChannel; invalid for other values of stype
    data: int       # the data we're examining. If -ve, means a DType.. above. If 0, means none. Positive is a DQ bit.
    col: str        # colour name for display

    @staticmethod
    def getDataItems():
        """Return a list of (name,int) tuples for the data fields"""
        x = [(name, val) for name, val in dq.DQs.items()]   # must all be > 0
        x.append(('NONE', DTypeNone))
        x.append(('UNC', DTypeUnc))
        x.append(('UNCTHR', DTypeUncThresh))
        return x

    def serialise(self):
        return {
            'stype': self.stype,
            'channel': self.channel,
            'data': self.data,
            'col': self.col
        }

    def deserialise(self, d):
        self.stype = d.get('stype', STypeMaxAll)
        self.channel = d.get('source', 0)
        self.data = d.get('data', DTypeNone)
        self.col = d.get('col', 'magenta')

    def __str__(self):
        return f"DQ(STYPE={self.stype} CHAN={self.channel} DAT={self.data} COL={self.col})"

    def __init__(self):
        self.deserialise({})
