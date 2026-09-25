"""
This is a sidecar loader for AUPE3 files (as of 25 Sep 2026)
"""
import logging
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple, Callable
from logging import getLogger
from pcot import ui
from pcot.ancillary import keys
from pcot.ancillary.multifile import MultifileSidecarLoader, add_multifile_sidecar_loader

logger = getLogger(__name__)

# multiply AUPE3's exposure_time by this to get seconds. It's already in seconds (a typical
# value is 0.009911), but it's kept as a constant in case a later convention differs.
EXPOSURE_TIME_TO_SECONDS = 1.0

# The ImageMetadata fields we read: AUPE3 field name -> (ancillary key, function converting the
# field's string value into the key's unit). Fields missing from a file are just left out.
FIELDS: Dict[str, Tuple[keys.AncillaryKey, Callable[[str], Any]]] = {
    "exposure_time": (keys.EXPOSURE, lambda v: float(v) * EXPOSURE_TIME_TO_SECONDS),
}


def _load(fname) -> Dict[str, Any]:
    """Read ancillary data from an AUPE XML metadata file. Raises an exception describing the
    problem if the file isn't in the format we expect, including if none of the fields in FIELDS
    are present. Once the file is recognised, a field with a bad value is left out with a warning
    (not an exception - no other loader will be asked to read the file)."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(fname)
    root = tree.getroot()
    cont = root.find("context")
    if cont is None:
        raise ValueError("no <context> element")

    metadata = [x for x in cont.findall("attribute") if x.get("name") == "metadata"]
    if len(metadata) == 0:
        raise ValueError("no metadata attribute in <context>")
    value = metadata[0].get("value")
    if value is None:
        raise ValueError("metadata attribute has no value")

    mds = value.split(";")
    mds = list(filter(lambda x: len(x) > 1, map(lambda x: x.split("="), mds)))
    mds = {x[0]: x[1] for x in mds}
    if "ImageMetadata" not in mds:
        raise ValueError("no ImageMetadata in metadata")

    md = mds["ImageMetadata"].split("|")
    md = dict(zip(md[::2], md[1::2]))
    if not any(field in md for field in FIELDS):
        raise ValueError(f"none of the expected fields ({', '.join(FIELDS)}) in ImageMetadata")

    output = {}
    for field, (key, convert) in FIELDS.items():
        if field not in md:
            logger.debug(f"{fname}: no {field} in ImageMetadata")
            continue
        try:
            output[key.name] = convert(md[field])
        except Exception as e:
            ui.log(f"Bad value for {field} in {fname} ({md[field]!r}): {e} - ignoring it",
                   loglevel=logging.WARNING)
    return output


class AUPE3MultifileLoader(MultifileSidecarLoader):
    def attempt_load(self, path: Path, problems: List[str]) -> Optional[Dict[str, Any]]:
        p = path.with_suffix(path.suffix + '.xml')  # look for AUPE's .png.xml style XML sidecar
        if not p.exists():
            return None
        try:
            return _load(p)
        except Exception as e:
            problems.append(f"AUPE3 loader could not read {p.name}: {e}")
            return None


# register the loader when this file is imported
add_multifile_sidecar_loader(AUPE3MultifileLoader())