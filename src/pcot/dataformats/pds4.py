import dataclasses
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from dateutil import parser
from proctools.products import DataProduct

import pcot
import pcot.dq

from pcot import ui
from pcot.datum import Datum
from pcot.filters import Filter
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.sources import External, MultiBandSource, Source


class PDS4Product:
    """A general purpose class for PDS4 products. Subclasses need to be dataclass objects so that the tricks
    in the serialisation work.
    Does not always store the actual data, but provides a way to access it. Otherwise just label information
    and metadata.

    Given that there is a DataProduct inside proctools, you might be wondering why we need this. Here's why:

    - One point of contact with proctools, so that if proctools changes we just need to change this.
    - We can add extra fields and methods to this class without changing proctools (e.g. index)
    - We need to be able to serialise this information
    - We need to be able to convert this information into a Datum object

    That last bit's awkward because we need a link to the original DataProduct. The problem then becomes
    that we end up with an awful lot of those in memory if these objects aren't deleted. So we need to be
    careful about how we use them.
    """

    lid: Optional[str]
    sol_id: Optional[int]
    start: Optional[datetime]
    idx: Optional[int]
    path: Optional[str]

    def __init__(self, p: Optional[DataProduct] = None):
        super().__init__()
        if p is not None:
            self.lid = p.meta.lid
            self.sol_id = int(p.meta.sol_id)  # a sol ID
            self.start = parser.isoparse(p.meta.start)
            self.p = p  # and store the original data product
            # record the full file path
            self.path = p.path
        else:
            self.lid = None
            self.sol_id = None
            self.start = None
            self.p = None
            self.path = None
        self.idx = 0  # and there should be an index which is used for vertical position on timeline

    def clear(self):
        """Clear the data product from memory (hopefully). We'll need to do a bit more than this to
        ensure all the data is gone, such as removing references to the arrays and so on. But this
        is a start."""
        self.p = None

    def load(self):
        """Reload the data product from the file if it's not there"""
        if self.path is None:
            raise ValueError("No path to reload from")
        elif self.p is None:
            self.p = DataProduct.from_file(Path(self.path))

    def serialise(self) -> Dict:
        """Serialise the product info into a dictionary which must contain prodtype"""
        return {'lid': self.lid,
                'sol_id': self.sol_id,
                'start': self.start.isoformat(),
                'idx': self.idx,
                'path': self.path,
                'prodtype': 'base'}

    def deserialise(self, d: Dict):
        """deserialise the product from a dictionary; static method creating new product.
        Should be called from a subclass deserialise static/class method"""
        self.lid = d['lid']
        self.sol_id = d['sol_id']
        self.start = parser.isoparse(d['start'])
        self.idx = d['idx']
        self.path = d['path']

    def long(self):
        return f"PDS4:{self.lid}\n Date {self.start} Index {self.idx} Sol {self.sol_id}"


class PDS4External(External):
    """A wrapper around PDS4 product info when used in a source."""

    def __init__(self, prod: PDS4Product):
        super().__init__()
        self.product = prod

    def long(self):
        return self.product.long()

    def brief(self):
        return "PDS4"

    def debug(self):
        """Return a string for debugging - just an abbreviated LID"""
        return f"pds4({self.product.lid[:20]})"

    def serialise(self):
        return 'pds4', self.product.serialise()

    @staticmethod
    def deserialise(data: Dict):
        """Deserialise the external product"""
        tp = data['prodtype']
        if tp == 'image':
            return PDS4External(PDS4ImageProduct.deserialise(data))
        else:
            raise ValueError(f"Unknown PDS4 product type {tp} in deserialisation")


class PDS4ImageProduct(PDS4Product):
    seq_num: Optional[int]
    camera: Optional[str]  # note - this is whether the camera is L or R, not PANCAM/AUPE.
    rmc_ptu: Optional[float]
    filt: Optional[Filter]

    def __init__(self, p: Optional[DataProduct] = None):
        """Given a data product"""
        super().__init__(p)
        if p is not None:
            m = p.meta
            self.seq_num = int(m.seq_num)
            self.camera = m.camera
            self.rmc_ptu = float(m.rmc_ptu)
            cwl = int(m.filter_cwl)
            fwhm = int(m.filter_bw)
            filtid = m.filter_id
            self.filt = Filter(cwl, fwhm, transmission=1.0, name=filtid, position=filtid)
        else:
            self.seq_num = None
            self.camera = None
            self.rmc_ptu = None
            self.filt = None

    def serialise(self) -> Dict:
        """Serialise the product into a dictionary"""
        d = super().serialise()
        d.update({'seq_num': self.seq_num,
                  'camera': self.camera,
                  'rmc_ptu': self.rmc_ptu,
                  'filt': self.filt.serialise(),
                  'prodtype': 'image'})
        return d

    @classmethod
    def deserialise(cls, d: Dict):
        """deserialise the product from a dictionary; static method creating new product"""
        x = cls()
        super(PDS4ImageProduct, x).deserialise(d)
        x.seq_num = d['seq_num']
        x.camera = d['camera']
        x.rmc_ptu = d['rmc_ptu']
        x.filt = Filter.deserialise(d['filt'])
        return x


def deserialiseProduct(d: Dict) -> PDS4Product:
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


class ProductList(list):
    """A list of PDS4Products which can be converted into a Datum object. They must all have the same type."""

    def __init__(self, *args):
        super().__init__(*args)

    def serialise(self) -> List:
        """Serialise the product list into a list"""
        return [x.serialise() for x in self]

    @staticmethod
    def deserialise(data: List) -> 'ProductList':
        lst = ProductList()
        for d in data:
            lst.append(deserialiseProduct(d))
        return lst

    def append(self, item):
        """Append an item to the list, ensuring the type is consistent."""
        if len(self) > 0 and not isinstance(item, type(self[0])):
            raise ValueError(f"Can't append {item} to list of {type(self[0])}")
        super().append(item)

    def insert(self, index, item):
        """Insert an item into the list, ensuring the type is consistent."""
        if len(self) > 0 and not isinstance(item, type(self[0])):
            raise ValueError(f"Can't insert {item} into list of {type(self[0])}")
        super().insert(index, item)

    def extend(self, iterable):
        """Extend the list with an iterable, ensuring the type is consistent."""
        for item in iterable:
            if len(self) > 0 and not isinstance(item, type(self[0])):
                raise ValueError(f"Can't extend list of {type(self[0])} with {item}")
        super().extend(iterable)

    def __setitem__(self, key, value):
        """Set an item in the list, ensuring the type is consistent."""
        if len(self) > 0 and not isinstance(value, type(self[0])):
            raise ValueError(f"Can't set list of {type(self[0])} with {value}")
        super().__setitem__(key, value)

    def clear(self):
        """Remove all the loaded products"""
        for p in self:
            p.clear()  # clear the product
            p.load()  # reload the product, but the actual data won't be reloaded until it is accessed

    def toDatum(self,
                mulValue: Optional[float] = 1,
                mapping: Optional[ChannelMapping] = None,
                inpidx: Optional[int] = None
                ) -> Datum:
        """Convert the product list into a Datum object. The optional arguments control how this is done,
        and depend on the type of the products."""

        if len(self) == 0:
            raise ValueError("Can't convert empty product list to Datum")
        # force load of all underlying DataProducts (but not their data)
        for p in self:
            p.load()
        # and do different things depending on the type of the products
        tp = type(self[0])  # which will be all the same
        if tp == PDS4ImageProduct:
            return self._toImageDatum(mulValue, mapping, inpidx)
        else:
            raise ValueError(f"Can't convert product list of type {tp} to Datum (yet)- TODO")

    def _toImageDatum(self, mulValue, mapping, inpidx) -> Datum:
        """Convert the product list into an image datum. Must be all image products,
        and the same size."""

        def getDQBits(data, uncertainty, dq):
            """Converts DQ data in the PDS4 QUALITY array into our DQ bits, and adds others
            depending on the other data too."""
            out = np.where(dq == 1, 0, pcot.dq.NODATA)  # where DQ is 1, output 0. Else output NODATA.
            out |= np.where(data > 0.9999999, pcot.dq.SAT,
                            0)  # where data is greater than or equal to 1 add the SAT bit
            out |= np.where(uncertainty == 0.0, pcot.dq.NOUNCERTAINTY, 0)  # set NOUNC bit if zero uncertainty data
            return out.astype(np.uint16)

        # get the data from each product and combine it

        try:
            imgdata = np.dstack([x.p.data for x in self]) * mulValue
            uncertainty = np.dstack([x.p.err for x in self])
            dq = np.dstack([getDQBits(x.p.data * mulValue, x.err, x.dq) for x in self])
        except ValueError as e:
            raise ValueError("Error in combining image products - are they all the same size?")

        # now handle the sources
        sources = MultiBandSource([Source()
                                  .setBand(p.filt)
                                  .setExternal(PDS4External(p))
                                  .setInputIdx(inpidx)
                                   for p in self])

        img = ImageCube(imgdata, rgbMapping=mapping, sources=sources,
                        uncertainty=uncertainty, dq=dq)

        return Datum(Datum.IMG, img)
