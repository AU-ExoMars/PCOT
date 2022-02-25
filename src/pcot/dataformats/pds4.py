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
        self.lid = None     # there's always a LID.
        pass

    def serialise(self) -> Dict:
        """Serialise the product into a dictionary"""
        pass

    @classmethod
    def deserialise(cls, d: Dict):
        """deserialise the product from a dictionary; static method creating new product"""
        pass


@dataclasses.dataclass()
class PDS4ImageProduct(PDS4Product):
    lid: str
    sol_id: int
    seq_num: int
    filt: Filter
    camera: str      # note - this is whether the camera is L or R, not PANCAM/AUPE.
    rmc_ptu: float
    start: datetime

    def serialise(self) -> Dict:
        """Serialise the product into a dictionary"""
        d = dataclasses.asdict(self)            # convert into a dict..
        d['start'] = self.start.isoformat()     # fixup the date into a string
        d['filt'] = self.filt.name              # and the filter with the camtype (so we can look it up)
        d['cameratype'] = self.filt.camera      # PANCAM or AUPE?
        d['prodtype'] = 'image'   # add type label
        return d

    @classmethod
    def deserialise(cls, d: Dict):
        """deserialise the product from a dictionary; static method creating new product"""
        # turn camera/filtername strings into a Filter (may throw)
        d['filt'] = filters.findFilter(d['cameratype'], d['filt'])
        del d['cameratype']
        # turn date string back into datetime
        d['start'] = parser.isoparse(d['start'])
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