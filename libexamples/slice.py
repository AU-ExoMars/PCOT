import numpy as np
import pcot
import pcot.datumfuncs as df
from pcot.datum import Datum,nullSourceSet
from pcot.dataformats import load
from pcot.dataformats.raw import RawLoader
from pcot.imagecube import ImageCube
import glob
import os.path
import cv2

SIZE = 100
STEPS = 20

pcot.setup()

raw = RawLoader(format=RawLoader.UINT16,
                width=1024,height=1024,
                bigendian=True,
                offset=48,
                rot=90)
                
# just the first 11
names = glob.glob("/media/sf_PancamData/SamplesGeologyFilter/*.bin")[:11]
names = [os.path.basename(x) for x in names]

d = load.multifile("/media/sf_PancamData/SamplesGeologyFilter/",names,
        rawloader=raw,
        filterpat=r".*Model-(?P<lens>L|R)(?P<n>[0-9][0-9]).*",
        mult=64,
        filterset="traininggeom")

img = d.get(Datum.IMG)

wavelengths = [img.wavelength(i) for i in range(img.channels)]
minw = min(wavelengths)
maxw = max(wavelengths)

print(wavelengths)

d = df.crop(d, 100, 100, 800, 800)
rgb = df.norm(df.merge(d%440,d%570,d%670))
rgb = df.resize(rgb,SIZE,SIZE,"linear")

rgb.get(Datum.IMG).rgbWrite("foo.png")


i = 0

for x in np.linspace(minw,maxw,STEPS):
    frame = df.norm(df.interp(d,x,SIZE))
    frame = df.merge(frame,frame,frame)
    frame = df.norm(frame * rgb)
    frame.get(Datum.IMG).rgbWrite(f"img{i}.png")
    i=i+1
    
