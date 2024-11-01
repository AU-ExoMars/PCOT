#!/usr/bin/env python

"""
Show the documentation state of all nodes
"""

import pcot
from pcot.parameters.taggedaggregates import TaggedDictType

pcot.setup()

for name, x in sorted(pcot.xform.allTypes.items()):
    if x.params is None:
        print(f"N {name} has a null params field")
    elif not isinstance(x.params,TaggedDictType):
        print(f"? {name} has a params field which is not a TD")
    else:
        print(f"Y {name} has autodocumentation")
        
    


