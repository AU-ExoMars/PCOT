"""
Template and example for a script which modifies graphs!
"""

import zipfile
import sys
import os
import shutil
import json


def traverse(fn,n,changed,path):
    if isinstance(n,dict):
        for k,v in n.items():
            # we have found a 'croi' - rectangle region of interest
            # so remove the last item (the isset)
            if k == 'croi':
                print(path, len(v),v)
                if len(v)>3:
                    n[k] = v[:-1]
                    changed |= True
            else:
                changed |= traverse(fn,v,changed,path+[k])        
    elif isinstance(n,list):
        for i,v in enumerate(n):
            changed |= traverse(fn,v,changed,path+[i])
    return changed    


def process(fn,data):
    d = json.loads(data)

    if traverse(fn,d,False,[]):        
        return True,json.dumps(d)
    return False,data        



def processfile(fn):
    # open old file for reading
    with zipfile.ZipFile(fn) as readzip:
        print(fn)
        # open new file for writing
        with zipfile.ZipFile("foo.zip","w",compression=zipfile.ZIP_DEFLATED) as writezip:
            for x in readzip.infolist():
                data = readzip.read(x.filename) # gives bytes

                # do any processing here!
                if x.filename == "JSON":
                    changed,data = process(fn,data)                

                writezip.writestr(x.filename,data)
#    if changed:
#        shutil.copyfile("foo.zip",fn)

for fn in sys.argv:
    if fn.endswith(".pcot"):
        processfile(fn)
