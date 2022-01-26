import dataclasses
from datetime import datetime
from typing import Dict

from dateutil import parser

from pcot import filters
from pcot.filters import Filter


class PDS4Product:
    """A general purpose class for PDS4 products. Subclasses need to be dataclass objects so that the tricks
    in the serialisation work."""

    def __init__(self):
        pass

    def serialise(self) -> Dict:
        """Serialise the product into a dictionary"""
        pass

    @classmethod
    def deserialise(cls, d: Dict):
        """deserialise the product from a dictionary; static method creating new product"""
        pass


@dataclasses.dataclass(frozen=True)
class PDS4ImageProduct(PDS4Product):
    sol_id: int
    seq_num: int
    filt: Filter
    camera: str
    rmc_ptu: float
    start: datetime

    def serialise(self) -> Dict:
        """Serialise the product into a dictionary"""
        d = dataclasses.asdict(self)            # convert into a dict..
        d['start'] = self.start.isoformat()     # fixup the date into a string
        d['filtname'] = self.filt.name          # and the filter with the camtype (so we can look it up)
        d['camera'] = self.filt.camera
        return d

    @classmethod
    def deserialise(cls, d: Dict):
        """deserialise the product from a dictionary; static method creating new product"""
        # turn camera/filtername strings into a Filter (may throw)
        d['filter'] = filters.findFilter(d['camera'], d['filtname'])
        del d['camera']
        del d['filtname']
        # turn date string back into datetime
        d['start'] = parser.isoparse(d['start'])
        # call constructor
        return cls(**d)
