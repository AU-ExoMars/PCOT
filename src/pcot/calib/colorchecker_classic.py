from pcot.calib.target import Target, CircularPatch

""" Geometry of the ColorChecker Classic."""
target = Target(
    width=1040,  # these are actually pixel dimensions in the image I'm working from
    height=693,

    regpoints=(
        # positions of corners
        (0, 0),  # top left corner
        (1040, 0),  # top right corner
        (0, 693),  # bottom left corner
        (1040, 693),  # bottom right corner
    ),
    instructions1="Click on the corners of the ColorChecker in the following order: top left, " \
                  "top right, bottom left, bottom right. ",
    instructions2="adjust the image of the ColorChecker by dragging the corner points " \
                  "or clicking 'rotate'. Then click 'generate ROIs'",

    patches=()  # we'll set these up below

)

# The ColorChecker Classic has 24 patches, arranged in 6 rows of 4 patches each.
pnames = ["dskin", "lskin", "sky", "foli", "flower", "bgreen",
          "orng", "purblu", "modred", "purp", "ygreen", "oyel",
          "B", "G", "R", "Y", "M", "C",
          "W", "N8", "N6.5", "N5", "N3.5", "BLK"]

pdescs = ["dark skin", "light skin", "sky blue", "foliage", "blue flower", "bluish green",
          "orange", "purplish blue", "moderate red", "purple", "yellow green", "orange yellow",
          "blue", "green", "red", "yellow", "magenta", "cyan",
          "white", "neutral 8", "neutral 6.5", "neutral 5", "neutral 3.5", "black"]


# colours in RGB space, range 0-1 for each.
# These come from https://babelcolor.com/colorchecker-2.htm#CCP2_data, using the Adobe values /255.
# They are really only there to give a visual representation so accuracy is not critical.
pcols = [
    (0.418557364, 0.324278097, 0.275065047),
    (0.714307288, 0.577413651, 0.502991936),
    (0.402039416, 0.47785905, 0.604431371),
    (0.377376128, 0.422647243, 0.270530768),
    (0.504944227, 0.500148234, 0.675431288),
    (0.51890221, 0.742252821, 0.666361312),
    (0.774066151, 0.480111931, 0.215312974),
    (0.311259378, 0.360795541, 0.644633317),
    (0.668710308, 0.331882082, 0.380117187),
    (0.32973503, 0.241756114, 0.403413662),
    (0.658092451, 0.73488172, 0.293074495),
    (0.827317204, 0.623769406, 0.218809623),
    (0.205295034, 0.254007332, 0.562180527),
    (0.39922623, 0.580036572, 0.306519589),
    (0.592389258, 0.208195148, 0.231596184),
    (0.89150617, 0.777719874, 0.206592478),
    (0.648006468, 0.332536302, 0.575488714),
    (0.257013814, 0.531442131, 0.642309687),
    (0.961007329, 0.960666647, 0.939843859),
    (0.78347933, 0.787457473, 0.78328787),
    (0.626068815, 0.629321888, 0.627846213),
    (0.468881192, 0.472758384, 0.47204003),
    (0.331113646, 0.334608661, 0.336276676),
    (0.208716029, 0.209057237, 0.21103277)]

# now build the patch data
idx = 0

x = 12 + 144 / 2  # centre point of first patch
y = 12 + 144 / 2

pitch = 176

for row in range(4):
    for col in range(6):
        target.patches += (CircularPatch(
            x + col * pitch,
            y + row * pitch,
            75,
            pnames[idx],
            pdescs[idx],
            pcols[idx]
        ),)
        idx += 1
