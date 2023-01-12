from typing import Union, Optional

# Source Types
from pcot import dq

# values of stype
STypeChannel = 1  # data comes from a single channel (the channel field gives the index in the canvas)
STypeMaxAll = 2  # data is max of all channels (or union if data>0 - it's a DQ bit)
STypeSumAll = 3  # data is sum of all channels (or union if data>0 - it's a DQ bit)

# values of data field, not including positive values which are DQ bit masks.
DTypeNone = 0  # inactive
DTypeUnc = -1  # for 'data' field in CanvasDQSpec, means uncertainty
DTypeUncThresh = -2  # for 'data', means a boolean: uncertainty>threshold


class CanvasDQSpec:
    stype: int  # source type, see above
    channel: int  # see STypeChannel; invalid for other values of stype
    data: int  # the data we're examining. If -ve, means a DType.. above. If 0, means none. Positive is a DQ bit.
    col: str  # colour name for display

    @staticmethod
    def getDataItems():
        """Return a list of (name,int) tuples for the data fields"""
        x = [(f"BIT:{name}", val) for name, val in dq.DQs.items()]  # must all be > 0
        x.append(('NONE', DTypeNone))
        x.append(('UNC', DTypeUnc))
        x.append(('UNCTHR', DTypeUncThresh))
        return x

    def isActive(self):
        """Is this DQ spec actually drawing anything?"""
        return self.data != DTypeNone

    def __init__(self, d=None):
        if d is None:
            d = {}
        self.stype = d.get('stype', STypeMaxAll)
        self.channel = d.get('channel', 0)
        self.data = d.get('data', DTypeNone)
        self.col = d.get('col', 'mag')

    def serialise(self):
        return {
            'stype': self.stype,
            'channel': self.channel,
            'data': self.data,
            'col': self.col
        }

    def __str__(self):
        return f"DQ(STYPE={self.stype} CHAN={self.channel} DAT={self.data} COL={self.col})"



coloursBase = {
    'red': (1.0, 0.0, 0.0),
    'green': (0.0, 1.0, 0.0),
    'blue': (0.0, 0.0, 1.0),
    'mag': (1.0, 0.0, 1.0),
    'cyan': (0.0, 1.0, 1.0),
    'yel': (1.0, 1.0, 0.0)
}

# now add 0 to the end of the tuple for non-flashing colours
colours = {n: c + (0,) for n, c in coloursBase.items()}
# and add the flashing colours with -f at the end of the name and 1 at the end of the tuple
colours.update({f"{n}-f": c + (1,) for n, c in coloursBase.items()})
