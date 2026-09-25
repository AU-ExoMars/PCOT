"""
The standard keys used in ancillary data dicts, and their units. Loaders must convert whatever
they read into these units, and should always refer to keys through the constants here (e.g.
keys.EXPOSURE.name), never as string literals - the set of keys is expected to change, and this
way a key can be renamed, given a different unit, or added in one place.
"""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class AncillaryKey:
    name: str           # the key used in ancillary data dicts
    unit: str           # the unit all loaders must convert to
    description: str    # human-readable description


EXPOSURE = AncillaryKey("exposure", "s", "Exposure time")

# all the keys, by name
ALL_KEYS: Dict[str, AncillaryKey] = {k.name: k for k in [
    EXPOSURE,
]}
