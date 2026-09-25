"""
This is a sidecar loader for AUPE3 files (as of 25 Sep 2026)
"""
from pathlib import Path
from typing import Any, Optional, Dict, List
from logging import getLogger
from pcot.ancillary import keys
from pcot.ancillary.multifile import MultifileSidecarLoader, add_multifile_sidecar_loader

logger = getLogger(__name__)

# multiply AUPE3's exposure_time by this to get seconds. ASSUMED to already be seconds
# (a typical value is 0.009911) - check this against the AUPE software.
EXPOSURE_TIME_TO_SECONDS = 1.0


def _load(fname) -> Dict[str, Any]:
    """Read ancillary data from an AUPE XML metadata file. Raises an exception describing the
    problem if the file isn't in the format we expect."""
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
    if "exposure_time" not in md:
        raise ValueError("no exposure_time in ImageMetadata")

    return {keys.EXPOSURE.name: float(md["exposure_time"]) * EXPOSURE_TIME_TO_SECONDS}


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