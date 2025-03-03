#!/usr/bin/env python3
DESC="""
Given camera data in the current directory, create a .parc file
from that data for use as camera parameter data.

"""

from pcot.cameras import filters,camdata

import yaml
import json
import argparse


def createFilters(filter_dicts):
    fs = {}
    for k,d in filter_dicts.items():
        f = filters.Filter(
            d["cwl"],
            d["fwhm"],
            transmission=d.get("transmission",1.0),
            name=k,
            position=d.get("position",k))
        fs[k]=f
    return fs

def run(args):
    with open(args.params) as f:
        d = yaml.safe_load(f)
    
        
        filters = createFilters(d["filters"])
        p = camdata.CameraParams(filters)
        store = camdata.CameraData.openStoreAndWrite(args.output,p)
        
        # add more data here
        
        store.close()
