import numpy as np
import pcot
from pcot import dq
from pcot.imagecube import ImageCube, ChannelMapping
from pcot.sources import MultiBandSource, nullSource, Source

rng = np.random.default_rng()

SIZE = (1024,1024)

def genfile(name,f,index):
    # loc is mean, scale is SD.
    data = rng.normal(loc=0.5, scale=0.2,size=SIZE).astype(np.float32)
    img = ImageCube(data,ChannelMapping(),MultiBandSource([nullSource]))
    img.rgbWrite(f"in_{name}_{f}_{index}.png")


for f in ["L01","L02","L03","L04"]:
    for i in range(0,10):
        genfile("foo",f,i)
