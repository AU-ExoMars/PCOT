import pcot
import pcot.datumfuncs as df
from pcot.utils.archive import FileArchive
from pcot.utils.datumstore import DatumStore
from pcot.value import Value
from pcot.datum import Datum
from pcot.sources import MultiBandSource,nullSource,nullSourceSet
import numpy as np
from pcot.imagecube import ImageCube,ChannelMapping
from pcot import dq

def gen_two_halves(w, h, v1, u1, v2, u2, doc=None, inpidx=None):
    """Generate an image of two halves. The top half is value v1 and uncertainty u1, the bottom half is v2,u2.
    Each of the values must be a tuple.
    """

    if doc is not None and inpidx is not None:
        # generate source names of the form r,g,b,c3,c4..
        sourceNames = ["r", "g", "b"] + [f"c{i}" for i in range(3, len(v1))]
        sources = MultiBandSource([Source().setBand(sourceNames[i]) for i in range(0, len(v1))])
    else:
        sources = MultiBandSource([nullSource] * len(v1))

    h2 = int(h/2)
    bands1 = np.dstack([np.full((h2, w), x) for x in v1]).astype(np.float32)
    bands2 = np.dstack([np.full((h2, w), x) for x in v2]).astype(np.float32)
    bands = np.vstack((bands1, bands2))
    unc1 = np.dstack([np.full((h2, w), x) for x in u1]).astype(np.float32)
    unc2 = np.dstack([np.full((h2, w), x) for x in u2]).astype(np.float32)
    uncs = np.vstack([unc1, unc2])

    assert bands.shape == (h, w, len(v1))
    imgc = ImageCube(bands, ChannelMapping(), sources, defaultMapping=None, uncertainty=uncs)
    assert imgc.w == w
    assert imgc.h == h
    return imgc



x = df.testimg(0)
y = df.testimg(1)


with FileArchive("multi.parc","w") as a:
    da = DatumStore(a)
    da.writeDatum("image0",x, description="testimg(0)")
    da.writeDatum("image1",y, description="testimg(1)")
    
    # and also write a few tiny images
    for i in range(0,10):
        r1 = i/9
        g1 = 1-r1
        b1 = (r1+g1)/2
        r2 = b1
        g2 = r1
        b2 = g1
        img = gen_two_halves(20,20,
            (r1,g1,b1),
            (r1*0.01,g1*0.01,b1*0.01),
            (r2,g2,b2),
            (0.01,0.01,0.01))
        d = Datum(Datum.IMG, img)
        da.writeDatum(f"smallimage{i}",d, description="a tiny image")
        
    # add a couple of vectors
    
    v = np.linspace(0, 1, 1000)
    u = v*0.1
    d = Datum(Datum.NUMBER, Value(v, u, dq.TEST), sources=nullSourceSet)
    da.writeDatum("testvec0", d, description="0-1, 1000 numbers")

    v = 1.0-np.linspace(0, 2, 200)
    d = Datum(Datum.NUMBER, Value(v, 0.2, dq.TEST), sources=nullSourceSet)
    da.writeDatum("testvec1", d, description="0-2, 200 numbers")
    
