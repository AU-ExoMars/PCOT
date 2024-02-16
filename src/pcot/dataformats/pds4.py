import dataclasses
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
from dateutil import parser
from proctools.products import DataProduct

import pcot
import pcot.dq

from pcot.datum import Datum
from pcot.filters import Filter
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.sources import External, MultiBandSource, Source


def show_meta_debug(m):
    """Collect property values and print them but also keep in a dict for debug breakpointing"""
    attrs = m._attrs
    props = {}
    for k in attrs:
        try:
            props[k] = getattr(m, k)
        except AttributeError:
            pass
    for k, v in props.items():
        print(k, v)



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
            self.path = str(p.path)
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
    """This is a PDS4 product which is an image. It has a few extra fields for the image data"""
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


class ProductList:
    """A list of PDS4Products which can be converted into a Datum object. They must all have the same type. It can be
    created from a list of DataProducts, in which case it will convert them into PDS4Products."""

    lst: List[PDS4Product]

    def __init__(self, lst: List[Union[PDS4Product, DataProduct]]):
        if len(lst) > 0:
            tp0 = type(lst[0])
            if not all([isinstance(x, tp0) for x in lst]):
                raise ValueError("All items in ProductList must be of the same type (DataProduct or PDS4Product)")
            if isinstance(lst[0], DataProduct):
                lst = self._createPDS4ProductList(lst)
            elif not isinstance(lst[0], PDS4Product):
                raise ValueError(f"ProductList must be created from DataProducts or PDS4Products, not {type(lst[0])}")

        # products with the same sol should have different indices
        # for positioning
        solcounts = {}
        for p in lst:
            idx = solcounts.get(p.sol_id, 0) + 1
            solcounts[p.sol_id] = idx
            p.idx = idx

        self.lst = lst

    @classmethod
    def _createPDS4ProductList(cls, data: List[DataProduct]):
        """Convert DataProducts into PDS4Products"""
        out = []
        for d in data:
            if d.type == "spec-rad":
                out.append(PDS4ImageProduct(d))
            else:
                raise ValueError(f"Can't create ProductList from DataProducts of type {d.type}")
        # we sort by camera, then freq, then bandwidth, then start
        out.sort(key=lambda p: (p.camera, p.filt.cwl, p.filt.fwhm, p.start))
        return out

    def serialise(self) -> List:
        """Serialise the product list into a list"""
        return [x.serialise() for x in self.lst]

    @classmethod
    def deserialise(cls, data: List) -> 'ProductList':
        lst = [deserialiseProduct(d) for d in data]
        return cls(lst)

    def clear(self):
        """Remove all the loaded products"""
        for p in self.lst:
            p.clear()  # clear the product
            p.load()  # reload the product, but the actual data won't be reloaded until it is accessed

    def toDatum(self,
                multValue: Optional[float] = 1,
                mapping: Optional[ChannelMapping] = None,
                selection: Optional[List[int]] = None,
                inpidx: Optional[int] = None
                ) -> Datum:
        """Convert the product list into a Datum object. The selection argument is a list of indices into the product
        list, which will be used to select only those products if present.
        The other optional arguments control how this is done,
        and depend on the type of the products.
        """

        selected = self.lst if selection is None else [self.lst[i] for i in selection]

        if len(selected) == 0:
            return Datum.null

        # force load of all underlying DataProducts (but not their data)
        for p in selected:
            p.load()

        # and do different things depending on the type of the selected products
        # which should be all the same
        tp = type(selected[0])
        # check that they are all the same type
        if not all([isinstance(x, tp) for x in selected]):
            raise ValueError("All products in the selection must be of the same type")

        if tp == PDS4ImageProduct:
            return ProductList._toImageDatum(selected, multValue, mapping, inpidx)
        else:
            raise ValueError(f"Can't convert product list of type {tp} to Datum (yet)- TODO")

    @staticmethod
    def _toImageDatum(selected: List[PDS4Product], multValue, mapping, inpidx) -> Datum:
        """Convert the selected list into an image datum. Must be all image products,
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
            # I'm converting to float32 here because I'm occasionally seeing errors in the ImageCube
            # constructor when the data is '>f4', which apparently is a different type to float32.
            def chk_float32(x):
                if x.dtype == '>f4':
                    return x.astype(np.float32)
                return x

            imgdata = chk_float32(np.dstack([x.p.data for x in selected]) * multValue)
            uncertainty = chk_float32(np.dstack([x.p.err for x in selected]))
            dq = np.dstack([getDQBits(x.p.data * multValue, x.p.err, x.p.dq) for x in selected])
        except ValueError as e:
            raise ValueError("Error in combining image products - are they all the same size?")

        # now handle the sources
        sources = MultiBandSource([Source()
                                  .setBand(p.filt)
                                  .setExternal(PDS4External(p))
                                  .setInputIdx(inpidx)
                                   for p in selected])

        img = ImageCube(imgdata, rgbMapping=mapping, sources=sources,
                        uncertainty=uncertainty, dq=dq)

        return Datum(Datum.IMG, img)
