"""
Template and example for a script which modifies graphs!
"""

import zipfile
import sys
import os
import shutil
import json

TEST_COMBO_NAMES_TO_SHORT_NAMES = {
    'Less than or equal to': 'le',
    'Greater than or equal to': 'ge',
    'Greater than': 'gt',
    'Less than': 'lt',
    'ALWAYS': 'always'
}


def process(fn,data):
    d = json.loads(data)
    changed = False
    
    for k,v in d['GRAPH'].items():
        if v['type'] == 'dqmod':
            if v['test'] in TEST_COMBO_NAMES_TO_SHORT_NAMES:
                v['mod'] = v['mod'].lower()
                v['data'] = v['data'].lower()
                v['test'] = TEST_COMBO_NAMES_TO_SHORT_NAMES[v['test']]
                changed = True
            
        
    return changed,json.dumps(d)


def processfile(fn):
    # open old file for reading
    with zipfile.ZipFile(fn) as readzip:
        print(fn)
        # open new file for writing
        with zipfile.ZipFile("foo.zip","w",compression=zipfile.ZIP_DEFLATED) as writezip:
            for x in readzip.namelist():
                data = readzip.read(x) # gives bytes

                # do any processing here!
                if x == "JSON":
                    changed,data = process(fn,data)

                writezip.writestr(x,data)
    if changed:
        print(f"{fn} changed")
        shutil.copyfile("foo.zip",fn)

for fn in sys.argv:
    if fn.endswith(".pcot"):
        processfile(fn)
