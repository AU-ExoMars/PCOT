#!/usr/bin/env python3
DESC="""
This script converts filter data from the older CSV format into
the YAML format used by the newer camera parameter system. The CSV data
itself may have been generated from a Markdown table by genfilters.py,
but should consist of name,position,cwl,fwhm,transmission (in any order).
"""


import csv
import sys
import os
import yaml
import argparse
from pathlib import Path
from dataclasses import dataclass,asdict

parser = argparse.ArgumentParser(description=DESC)
parser.add_argument('input',metavar="FILENAME",type=str)


@dataclass
class FilterData:
    cwl: int
    fwhm: int
    transmission: float
    position: str


def load(path: Path):
    """Load a filter set from a file and store in the internal dict"""

    def decomment(csvfile):  # comments are like those in Python
        for row in csvfile:
            raw = row.split('#')[0].strip()
            if raw:
                yield raw

    # build a list of filters
    filters = {}
    with open(os.path.expanduser(path)) as file:
        for r in csv.DictReader(decomment(file)):
            f = FilterData(int(r['cwl']),
                           int(r['fwhm']),
                           float(r['transmission']),
                           r['position'])
            filters[r['name']]=f
    return filters



args = parser.parse_args()

filters = load(args.input)
filters = {k:asdict(v) for k,v in filters.items()}

d = { "filters": filters }
print(yaml.dump(d))
