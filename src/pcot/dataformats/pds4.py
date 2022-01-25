from dataclasses import dataclass, fields
from typing import Dict


class PDS4Product:
    """A general purpose class for PDS4 products. These are stored inside the Requires ability to serialise to some extent."""

    def __init__(self):
        pass

    def serialise(self) -> Dict:
        """Serialise the product into a dictionary"""
        return {x.name: getattr(self, x.name) for x in fields(self)}

    @classmethod
    def deserialise(cls, d: Dict):
        """deserialise the product from a dictionary; static method creating new product"""
        # set of args to pass to the constructor
        kwargs = {x.name: d[x.name] for x in fields(cls)}
        # construct with those args
        return cls(**kwargs)


@dataclass(frozen=True)
class PDS4ImageProduct(PDS4Product):
    sol_id: int = 0
    seq_num: int = 0
    filter_cwl: float = 0
    filter_id: str = ""
    camera: str = ""
    rmc_ptu: float = 0


