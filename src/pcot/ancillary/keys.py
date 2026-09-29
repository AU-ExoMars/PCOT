"""
The standard keys used in ancillary data dicts, and their units. Loaders must convert whatever
they read into these units, and should always refer to keys through the constants here (e.g.
keys.EXPOSURE.name), never as string literals - the set of keys is expected to change, and this
way a key can be renamed, given a different unit, or added in one place.

Values stored under these keys must be JSON-serialisable (see BandAncillary).
"""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class AncillaryKey:
    name: str           # the key used in ancillary data dicts
    unit: str           # the unit all loaders must convert to
    description: str    # human-readable description


EXPOSURE = AncillaryKey("exposure", "s", "Exposure time")
# The filter a band was captured through, as the camera's own filter wheel number and lens. These are
# raw facts from the capture: matching them to a filter in PCOT's camera data is done by the image
# loader, which knows the camera (see load.multifile()).
FILTER_NUMBER = AncillaryKey("filter_number", "", "Filter wheel position number (an int)")
LENS = AncillaryKey("lens", "", "Lens the band was captured through: 'L' or 'R'")

# all the keys, by name
ALL_KEYS: Dict[str, AncillaryKey] = {k.name: k for k in [
    EXPOSURE,
    FILTER_NUMBER,
    LENS,
]}
