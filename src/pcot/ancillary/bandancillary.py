"""
Per-band ancillary data for an ImageCube. See internalDocs/docs/ancillary.md for the rules about
which operations keep it and which drop it.
"""
from typing import List, Dict, Any, Optional, Iterable


class BandAncillary:
    """Ancillary data for each band of an ImageCube: one dict per band, keyed by the names in
    pcot.ancillary.keys. A band with no ancillary data has an empty dict. The API deliberately
    mirrors MultiBandSource, so code which rearranges bands can do the same thing to both.

    ASSUMPTION: although the values are typed as Any, they must be JSON-serialisable (str, int,
    float, bool, None, or lists/dicts of those - not e.g. numpy scalars), because they are saved
    as-is in documents and PARC archives. A value which isn't will make saving fail, with an error
    from the archive code naming the offending item."""
    bands: List[Dict[str, Any]]

    def __init__(self, bands: List[Dict[str, Any]]):
        self.bands = bands

    @classmethod
    def empty(cls, n: int) -> 'BandAncillary':
        """Create ancillary data with nothing in it for n bands"""
        return cls([{} for _ in range(n)])

    @classmethod
    def concat(cls, lst: Iterable['BandAncillary']) -> 'BandAncillary':
        """Join the bands of several BandAncillary objects together, in order (e.g. when merging images)"""
        return cls([dict(d) for a in lst for d in a.bands])

    def copy(self) -> 'BandAncillary':
        return BandAncillary([dict(d) for d in self.bands])

    def select(self, bands: List[int]) -> 'BandAncillary':
        """Get the data for a subset (or reordering) of the bands"""
        return BandAncillary([dict(self.bands[i]) for i in bands])

    def get(self, key: str) -> List[Optional[Any]]:
        """Get the value of a key for every band, with None for bands which don't have it"""
        return [d.get(key) for d in self.bands]

    def serialise(self) -> List[Dict[str, Any]]:
        """Serialise as a list of dicts, one per band (the values must be JSON-serialisable)"""
        return [dict(d) for d in self.bands]

    @classmethod
    def deserialise(cls, lst: List[Dict[str, Any]]) -> 'BandAncillary':
        return cls([dict(d) for d in lst])

    def isEmpty(self) -> bool:
        """True if no band has any ancillary data"""
        return not any(self.bands)

    def __len__(self):
        return len(self.bands)

    def __getitem__(self, band: int) -> Dict[str, Any]:
        return self.bands[band]

    def __repr__(self):
        return f"BandAncillary({self.bands})"
