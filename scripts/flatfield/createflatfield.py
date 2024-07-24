#!/usr/bin/env python

"""
This script assumes there are a number of files present in the current
directory with names of the form

    in_<name>_<wavelength>_<index>.png

For example,

    in_darkaupe_440_0.png
    
It will load all the files for each distinct name and wavelength as 1-band
images and average them into a single 1-band image, with the uncertainty of
each pixel calculated from the input images.

They will then all be merged into a single n-band data archive

    out_<name>.zip
"""

import re
from os import listdir
from os.path import isfile, join
import pcot
from pcot.dataformats import load
from pcot.dataformats import envi
from pcot.datum import Datum
from pcot.filters import Filter,getFilter
from pcot.sources import MultiBandSource, Source, StringExternal
from pcot.utils.archive import FileArchive
from pcot.utils.datumstore import DatumStore

import pcot.datumfuncs as df

FILTERSET = 'AUPE'
CAMNAME = 'LWAC'

pcot.setup()

def readfiles():
    # this returns a dictionary of dictionaries - the outer dictionary, keyed
    # by name, contains a dictionary keyed by filterpos, which contains a list
    # of filenames.

    regex = re.compile(r"in_(?P<name>[A-Za-z0-9]+)_(?P<filterpos>[A-Z0-9]+)_(?P<index>[0-9]+)\.png")
    data = dict()
    
    # get the files from the current directory
    filenames = [f for f in listdir(".") if isfile(f)]
    
    # iterate over them and create a data item for each match
    for x in filenames:
        m = regex.match(x)
        if m is not None:
            m = m.groupdict()
            name = m['name']
            if name not in data:
                data[name]=dict()
            d = data[name]
            filt = m['filterpos']
            if filt not in d:
                d[filt] = []
            d[filt].append(x)
            
    return data
    

    
def process(data):
    for name,d in data.items():
        band_images = []
        print(f"{name} has {len(d)} filters")
        with FileArchive(f"out_{name}.parc","w") as fa, DatumStore(fa) as a:
            for filterpos,filenames in d.items():
                # get the filter data for this filter
                filter = getFilter(FILTERSET,filterpos,search='pos')
                if filter.cwl == 0:
                    raise Exception(f"cannot find filter {filterpos}")
                # we have a list of filenames. Let's load them all in as a single image.
                datum = load.multifile(".",filenames)
                # we now have a multi-band image! Let's greyscale that image. This will also aggregate the uncertainties.
                img = df.grey(datum).get(Datum.IMG)
                # set the source to be the filter we're using
                source = Source().setBand(filter).setExternal(StringExternal("createflatfield","creatflatfield"))
                img.sources = MultiBandSource([source])
                band_images.append(img)
            # now merge all the individual band images - have to wrap in Datum first and then
            # expand!
            img = df.merge(*[Datum(Datum.IMG,x) for x in band_images])
            a.writeDatum("main",img,description="Flat/darkfield data")
        

process(readfiles())
