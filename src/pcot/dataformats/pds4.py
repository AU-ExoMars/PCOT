import dataclasses
from datetime import datetime
from typing import Dict

from dateutil import parser

from pcot import filters
from pcot.filters import Filter


class PDS4Product:
    """A general purpose class for PDS4 products. Subclasses need to be dataclass objects so that the tricks
    in the serialisation work.
    Does not store the actual data! Just label information and metadata."""

    def __init__(self):
        self.lid = ""     # there's always a LID.
        self.idx = 0        # and there should be an index which is used for vertical position on timeline
        self.sol_id = 0     # and a sol ID
        self.start = 0      # and a datetime

    def serialise(self) -> Dict:
        """Serialise the product info into a dictionary"""
        pass

    @classmethod
    def deserialise(cls, d: Dict):
        """deserialise the product from a dictionary; static method creating new product"""
        pass


@dataclasses.dataclass()
class PDS4ImageProduct(PDS4Product):
    lid: str
    idx: int
    start: datetime
    sol_id: int

    seq_num: int
    filt: Filter
    camera: str      # note - this is whether the camera is L or R, not PANCAM/AUPE.
    rmc_ptu: float

    def serialise(self) -> Dict:
        """Serialise the product into a dictionary"""
        d = dataclasses.asdict(self)            # convert into a dict..
        d['start'] = self.start.isoformat()     # fixup the date into a string
        d['filt'] = self.filt.serialise()
        d['prodtype'] = 'image'   # add type label
        return d

    @classmethod
    def deserialise(cls, d: Dict):
        """deserialise the product from a dictionary; static method creating new product"""
        # turn filter element back into a real filter
        d['filt'] = filt = Filter.deserialise(d['filt'])
        # turn date string back into datetime
        d['start'] = parser.isoparse(d['start'])

        # eliminate fields whose names aren't attributes of this class. We do this
        # because of weird version problems.
        attrs = [x.name for x in dataclasses.fields(cls)]
        d = {k: d[k] for k in attrs}

        # call constructor
        return cls(**d)


def deserialise(d: Dict) -> PDS4Product:
    """Deserialise any kind of PDS4Product"""
    try:
        tp = d['prodtype']
    except KeyError:
        raise Exception(f"no product type in dictionary to deserialise")

    del d['prodtype']
    if tp == 'image':
        return PDS4ImageProduct.deserialise(d)
    else:
        raise Exception(f"unknown product type: {tp}")