#
# PCT geometry
#

# Numbering system is from the top left, as viewed in EXM-PC-DRW-ABU-0007_1.4_PCT_Drawing
# with the two large patches at the bottom. Tuples give x,y coordinates and radius in mm; origin is TOP LEFT.
# Note that the patches are elliptical, but the mean diameters are 19mm/31mm for small/large.

patches = [
    (12.50, 11, 9.5),        # 0     dark grey       Schott NG4      |
    (33.50, 11, 9.5),        # 1     red             Schott RG610    |
    (54.50, 11, 9.5),        # 2     dark blue       Schott NG3      | small glass patches
    (12.50, 32, 9.5),        # 3     mid grey        Schott NG11     |
    (33.50, 32, 9.5),        # 4     yellow          Schott OG515    |
    (54.50, 32, 9.5),        # 5     cyan            Schott BG18     |

    (17, 59, 15.5),           # 6     white           Pyroceram           | large patches
    (50, 59, 15.5)            # 7     pink            WCT-2065            |
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

