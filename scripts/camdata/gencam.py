from pcot.cameras import filters,camdata

import yaml
import json


def createFilters(filter_dicts):
    for k,d in filter_dicts.items():
        f = filters.Filter(
            d["cwl"],
            d["fwhm"],
            transmission=d.get("transmission",1.0),
            name=k,
            position=d.get("position",k))
        



with open("params.yaml") as f:
    d = yaml.safe_load(f)

    
#    s = json.dumps(d,indent=4)
#    print(s)

    filters = createFilters(d["filters"])    

    p = camdata.CameraParams(filters)
    
    camdata.CameraData.write("example.parc",p)
