#
# PCT geometry
#

# Numbering system is from the top left, as viewed in EXM-PC-DRW-ABU-0007_1.4_PCT_Drawing
# with the two large patches at the bottom. Tuples give x,y coordinates and radius in mm; origin is TOP LEFT.
# Note that the patches are elliptical, but the mean radii are 19mm/31mm for small/large.

patches = [
    (12.50, 11, 19),        # 0     dark grey       Schott NG4      |
    (33.50, 11, 19),        # 1     red             Schott RG610    |
    (54.50, 11, 19),        # 2     dark blue       Schott NG3      | small glass patches
    (12.50, 41, 19),        # 3     mid grey        Schott NG11     |
    (33.50, 41, 19),        # 4     yellow          Schott OG515    |
    (54.50, 41, 19),        # 5     cyan            Schott BG18     |

    (17, 66, 31),           # 6     white           Pyroceram           | large patches
    (50, 66, 31)            # 7     pink            WCT-2065            |
]

# positions of the three large screws (not the corner holes)

screws = [
    (4.49, 21.25),          # left edge screw
    (62.51, 21.25),         # right edge screw
    (33.50, 71.50)          # bottom edge screw
]

# overall dimensions

width = 67
height = 76

