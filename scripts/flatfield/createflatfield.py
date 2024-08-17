#!/usr/bin/env python

"""
Each directory contains images for a single filter. The images we are
interested in for creating flat fields are those captured at 80% saturation,
of which there are 10.

These are averaged into a single image per band, and these are then composed
into a single multiband image. If any pixel in any of the input images 
is saturated, the output pixel is marked as saturated in that band. If the
uncertainty of that pixel is zero, all the input images had a saturated
pixel.

"""


import re
from typing import Dict,List
from os import listdir
from os.path import isfile, isdir, join
import numpy as np

import pcot
from pcot import dq
from pcot.datum import Datum
from pcot.filters import Filter,getFilter,loadFilterSet
from pcot.sources import MultiBandSource, Source, StringExternal
from pcot.utils.archive import FileArchive
from pcot.utils.datumstore import DatumStore
from pcot.dataformats import load
from pcot.dataformats.raw import RawLoader
from pcot.dataformats import envi
import pcot.datumfuncs as df

pcot.setup()

# this is the training set of filters, filter wheel 1 (geometry)
pcot.filters.loadFilterSet("training-geom","training1.csv")

# set up a raw loader
loader = RawLoader(format=RawLoader.UINT16,width=1024,height=1024,bigendian=True,
    rot=90,offset=48)
    

OUTPUT = "flatfield.parc"



# Step 1 - create the file lists, one for each filter. These are keyed by
# filter position e.g. "R3"

def gen_file_lists() -> Dict[str,List]:
    """Find image directories, and find 10 files with the same exposure in each."""
    out = {}
    
    regex = re.compile(r"[0-9]{8}_[0-9]{6}_WAC.*_(?P<pos>(L|R)[0-9]+)_.*")
    for f in listdir("."):
         if isdir(f):
            m = regex.match(f)
            if m is not None:
                # we have a directory name that matches; now get the files therein.
                pos = m['pos']
                # store a tuple of dir and files
                out[pos] = (f,get_file_list(f,pos))

    return out                
                

def get_file_list(dir,pos)-> List[str]:
    """Given a directory, return a list of the files we should process. There should be 10 at the same exposure."""
    
    # we go through the files, keeping a dict of time->fileswiththattime
    filesbytime = {}
    # annoyingly the date and position formats are different from in the directory names!
    regex = re.compile(r"[0-9]{6}_[0-9]{6}_Training Model-(?P<pos>(L|R)[0-9]+)_\+[0-9]{3}_(?P<time>[0-9\.]+)m?s.*.bin")
    for f in listdir(dir):
        m = regex.match(f)
        if m is not None:
            t = m['time']
            pos2 = m['pos']
            # check the pos is the same
            if pos2[0] != pos[0] or int(pos2[1:]) != int(pos[1:]):
                raise Exception(f"Position {pos2} does not agree with {pos} given in the directory")
            if t not in filesbytime:
                filesbytime[t] = []
            filesbytime[t].append(f)
    
    # now return the list of files which has 10 entries
    for v in filesbytime.values():
        if len(v)==10:
            return v
            
    for k,v in filesbytime.items():
        print(k,len(v))

    raise Exception("cannot find a set of files with 10 exposures")
    return files
    

def process(pos, dir, lst):
    """For a position, process a list of files"""
    band_images = []
    print(f"{pos} has {len(lst)} filters")
    
    # irritatingly, the filters are named R1, R2, and not R01, R02..
    
    if len(pos)==2:
        pos = pos[0]+"0"+pos[1]

    filter = getFilter("training-geom",pos,search="pos")
    if filter.cwl == 0:
        raise Exception(f"cannot find filter {pos}")

    # load the files into one big image, getting the filters right
    print(lst)        
    img = load.multifile(dir,lst,
        filterpat=".*/[0-9]{6}_[0-9]{6}_Training Model-(?P<lens>(L|R))(?P<n>[0-9]+).*",
        bitdepth=10,
        filterset="training-geom",
        rawloader=loader)
        
    # now we want to set the SAT bit on all saturated pixels
    cube = img.get(Datum.IMG)
    # clear all the NOUNC bits
    cube.dq &= ~dq.NOUNC
    bitsToChange = np.where(cube.img == 1.0, dq.SAT, 0).astype(np.uint16)
    print(f"   {np.count_nonzero(bitsToChange)} pixels are saturated")
    cube.dq |= bitsToChange

    
    # greyscale that image - find the mean across all pixels -  which will aggregate uncertainties
    img = df.grey(img)

    print(f"Wavelength {img.get(Datum.IMG).wavelength(0)}")
    print(f"  As read: range({df.min(img)},{df.max(img)}), mean={df.mean(img)},sd={df.sd(img)}")


    # now divide the new 1-band image by the mean of all its pixels
    img = img/df.mean(img)
    
    print(f"  Result after div by mean range({df.min(img)},{df.max(img)}), mean={df.mean(img)},sd={df.sd(img)}")
    return img
        

# run the process on every band
bands = []
for pos,v in gen_file_lists().items():
    if len(pos)==2:
        pos = pos[0]+"0"+pos[1]
    directory,lst = v
    bands.append(process(pos,directory,lst))
        
# merge all the images

img = df.merge(*bands)

# and write to a PARC

with FileArchive(OUTPUT,"w") as fa, DatumStore(fa) as a:
    a.writeDatum("main",img,description="Flat/darkfield data")

# and an ENVI (without uncertainty)

envi.write("flatfield_n.envi",img.get(Datum.IMG),"RWAC")
envi.write("flatfield_u.envi",df.uncertainty(img).get(Datum.IMG),"RWAC")
