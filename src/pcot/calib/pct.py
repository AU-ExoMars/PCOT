"""Geometry of the PCT.

patches: the positions, radii, names and approx. colours of the PCT patches

Order of the patches is from the top left, as viewed in EXM-PC-DRW-ABU-0007_1.4_PCT_Drawing
with the two large patches at the bottom. Each patch has x,y coordinates and radius in mm, with origin
at top left; the patch name, and an RGB approximation of its colour.
Note that the patches are elliptical, but the mean diameters are 19mm/31mm for small/large.

screws: the positions of the three large mounting screws (not the corner holes)

width, height: overall PCT dimensions

"""

from collections import namedtuple

Patch = namedtuple('Patch', ['x', 'y', 'r', 'name', 'col'])

patches = [
    Patch(12.50, 11, 9.5, "NG4/dkgrey", (0.4, 0.4, 0.4)),
    Patch(33.50, 11, 9.5, "RG610/red", (1, 0, 0)),
    Patch(54.50, 11, 9.5, "NG3/blue", (0, 0, 1)),
    Patch(12.50, 32, 9.5, "NG11/ltgrey", (0.7, 0.7, 0.7)),
    Patch(33.50, 32, 9.5, "OG515/yellow", (1, 1, 0)),
    Patch(54.50, 32, 9.5, "BG18/cyan", (0, 1, 1)),

    Patch(17, 59, 15.5, "Pyro/white", (1,1,1)),
    Patch(50, 59, 15.5, "WCT-2065/pink", (1,0.7,0.7))
]

# positions of the three large screws (not the corner holes)

screws = [
    (4.49, 21.25),  # left edge screw
    (62.51, 21.25),  # right edge screw
    (33.50, 71.50)  # bottom edge screw
]

# overall dimensions

width = 67
height = 76
