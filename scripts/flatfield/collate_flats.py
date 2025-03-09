"""
This is an example script to show how you might possibly 
arrange and collect flatfield files into groups for processing.

What we want to end up with is a directory of files for each filter which
we can process.

This script:
    * Finds all image files 
    * Extracts their filter position and exposure time
    * For each filter, finds a list of files which have the largest number of exposures
      (for example, there could be 10 files with a 140s exposure but only 2 with a 240s exposure,
      so we return the former files). This is because we need to average as many files as we
      can but they must all be the same exposure.
    * Copy the files into a directory for each filter.
    
We still need to do the actual processing into single flatfield images for each filter:
    * for each image, set saturated bits in the DQ
    * if any (or all?) images are saturated at a particular pixel, mark uncertainty as zero
    * OR all the DQ bits together across all images
    * average the images nominal values and process uncertainty too (should be done automatically)
"""

import re
from typing import Dict,List
import os
import glob
import shutil
import argparse
from pathlib import Path
from dataclasses import dataclass

parser = argparse.ArgumentParser(description="Collate images by filter for processing")
parser.add_argument("input",metavar="INPUT_DIRECTORY",type=str,help="All files below this will be scanned")
parser.add_argument("output",metavar="OUTPUT_DIRECTORY",type=str,help="This directory will be created if needed")

args = parser.parse_args()

# This is the file format we want
format= ".bin"


# This regular expression is used both match image files, and also get the filter position
# and exposure time.
regex = re.compile(r"[0-9]{6}_[0-9]{6}_Training Model-(?P<pos>(L|R)[0-9]+)_\+[0-9]{3}_(?P<exp>[0-9\.]+)m?s.*"+format)

@dataclass
class ImageFile:
    path: str
    exp: str
    pos: str
    

def gen_file_lists(directory) -> Dict[str,List]:
    """Find all the images and return them as File objects."""
    files = []

    for path in glob.glob(os.path.join(directory,f"**/*{format}"),recursive=True):
        m = regex.match(os.path.basename(path))
        if m is not None:
            files.append(ImageFile(path,m['exp'],m['pos']))
            
    return files

    

def find_files_with_largest_exposure(files,pos):
    """Given a list of files, find the largest number of files with the same exposure for a
    given filter position and return those files"""
    
    files = [f for f in files if f.pos==pos]
    # add files to a dict of lists, keyed by exposure time
    exposures = {}
    for x in files:
        # really must remember this idiom. If key is in dict, return value, else add [] and return it.
        exposures.setdefault(x.exp,[]).append(x)
    # return the list with the most members
    res = exposures[max(exposures,key=lambda x: len(exposures.get(x)))]
    print(f"{pos} has {len(res)} files at exposure {res[0].exp}")
    return res


def build_file_sets_with_most_exposures(files):
    """Create a directory for each filter, and for each filter copy the files which all share
    the largest number of exposures into that directory"""

    # get all the filters    
    filters = set([x.pos for x in files])
    print("Filters are:", ",".join(filters))
    
    # for each filter, get the largest set of files which share the same exposure time
    for pos in filters:
        fs = find_files_with_largest_exposure(files,pos)
        
        # create a directory for the filter
        path = Path(os.path.join(args.output,pos))
        path.mkdir(parents=True,exist_ok=True)
        
        # and copy the files into it
        for x in fs:
            shutil.copy(x.path,path)


    
# Get all the image files in (and below) the directory
files = gen_file_lists(args.input)

build_file_sets_with_most_exposures(files)

